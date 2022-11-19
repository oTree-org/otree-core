import json
from starlette.background import BackgroundTask
import re

import wtforms
from starlette.endpoints import HTTPEndpoint
from starlette.responses import JSONResponse, RedirectResponse, Response
from wtforms import validators as wtvalidators, widgets as wtwidgets
from wtforms.fields import html5 as h5fields

import otree
import otree.bots.browser
import otree.channels.utils as channel_utils
import otree.common
import otree.models
import otree.views.cbv
from otree import export
from otree import settings
from otree.common import (
    get_models_module,
    DebugTable,
    AUTH_COOKIE_NAME,
    AUTH_COOKIE_VALUE,
)
from otree.constants import ADVANCE_SLOWEST_BATCH_SIZE
from otree.currency import RealWorldCurrency
from otree.database import values_flat, save_sqlite_db, db
import otree.database
from otree.models import Session
from otree.session import SESSION_CONFIGS_DICT, SessionConfig
from otree.templating import get_template_name_if_exists
from otree.views.cbv import AdminSessionPage, AdminView
from . import cbv
from .cbv import enqueue_admin_message

validators_required = [wtvalidators.InputRequired()]


def pretty_name(name):
    """Converts 'first_name' to 'first name'"""
    if not name:
        return ''
    return name.replace('_', ' ')


class CreateSessionForm(wtforms.Form):
    session_configs = SESSION_CONFIGS_DICT.values()
    session_config_choices = [(s['name'], s['display_name']) for s in session_configs]

    session_config = wtforms.SelectField(
        choices=session_config_choices,
        validators=validators_required,
        render_kw=dict({'class': 'form-select'}),
    )

    num_participants = wtforms.IntegerField(
        validators=[wtvalidators.DataRequired(), wtvalidators.NumberRange(min=1)],
        render_kw={'autofocus': True, 'class': 'form-control w-auto'},
    )

    # too much weirdness with BooleanField and 'y'
    # so we render manually
    # it's a booleanfield so its default value will be 'y',
    # but it's a hidden widget that we are passing to the server
    # through .serializeArray, so we need to filter out
    is_mturk = wtforms.BooleanField()
    room_name = wtforms.StringField(widget=wtwidgets.HiddenInput())

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if self.is_mturk.object_data:
            label = "Number of MTurk workers (assignments)"
            description = (
                'Since workers can return an assignment or drop out, '
                'some "spare" participants will be created: '
                f'the oTree session will have {settings.MTURK_NUM_PARTICIPANTS_MULTIPLE} '
                'times more participant objects than the number you enter here.'
            )
        else:
            label = "Number of participants"
            description = ''

        self.num_participants.label = label
        self.num_participants.description = description

    def validate(self):
        if not super().validate():
            return False

        config = SESSION_CONFIGS_DICT[self.session_config.data]
        lcm = config.get_lcm()
        if self.num_participants.data % lcm:
            self.num_participants.errors.append(
                'Please enter a valid number of participants.'
            )
        return not bool(self.errors)


class CreateSession(cbv.AdminView):
    template_name = 'otree/CreateSession.html'
    url_pattern = '/create_session'

    def get_form(self):
        # need to pass is_mturk because it uses a different label.
        return CreateSessionForm(
            is_mturk=bool(self.request.query_params.get('is_mturk'))
        )

    def get_context_data(self, **kwargs):
        x = super().get_context_data(
            configs=SESSION_CONFIGS_DICT.values(),
            # splinter makes request.GET.get('mturk') == ['1\\']
            # no idea why
            # so just see if it's non-empty
            **kwargs,
        )
        return x


class SessionSplitScreen(AdminSessionPage):
    '''Launch the session in fullscreen mode
    only used in demo mode
    '''

    def vars_for_template(self):
        participant_urls = [
            self.request.base_url.replace(path=participant._start_url())
            for participant in self.session.get_participants()
        ]
        return dict(session=self.session, participant_urls=participant_urls)


class SessionStartLinks(AdminSessionPage):
    def vars_for_template(self):
        session = self.session
        room = session.get_room()
        from otree.models import Participant

        p_codes = values_flat(
            session.pp_set.order_by('id_in_session'), Participant.code
        )
        participant_urls = []
        for code in p_codes:
            rel_url = otree.common.participant_start_url(code)
            url = self.request.base_url.replace(path=rel_url)
            participant_urls.append(url)

        context = dict(
            use_browser_bots=session.use_browser_bots, participant_urls=participant_urls
        )

        if room:
            context.update(
                room_wide_url=room.get_room_wide_url(self.request),
                room=room,
                collapse_links=True,
            )
        else:
            from otree.asgi import reverse

            anonymous_url = self.request.base_url.replace(
                path=reverse(
                    'JoinSessionAnonymously', anonymous_code=session._anonymous_code
                )
            )

            context.update(
                anonymous_url=anonymous_url,
                num_participants=len(participant_urls),
                splitscreen_mode_on=len(participant_urls) <= 3,
            )

        return context


class SessionEditPropertiesForm(wtforms.Form):
    participation_fee = wtforms.DecimalField()
    real_world_currency_per_point = wtforms.DecimalField(places=6)
    label = wtforms.StringField()
    comment = wtforms.TextAreaField(render_kw=dict(rows='3', cols='40'))

    field_names = [
        'participation_fee',
        'real_world_currency_per_point',
        'label',
        'comment',
    ]


class SessionEditProperties(AdminSessionPage):

    form_class = SessionEditPropertiesForm

    def get_form(self):
        session = self.session
        config = session.config

        form = SessionEditPropertiesForm(
            data=dict(
                participation_fee=config['participation_fee'],
                real_world_currency_per_point=config['real_world_currency_per_point'],
                label=session.label,
                comment=session.comment,
            )
        )
        if session.mturk_HITId:
            form.participation_fee.widget = wtwidgets.HiddenInput()
        return form

    def form_valid(self, form):
        session = self.session
        session.label = form.label.data
        session.comment = form.comment.data

        participation_fee = form.participation_fee.data
        # convert to float because that's the usual type for rwc_per_point
        # it shouldn't behave differently after you edit session properties
        rwc_per_point = float(form.real_world_currency_per_point.data)

        config = session.config.copy()
        if participation_fee is not None:
            config['participation_fee'] = RealWorldCurrency(participation_fee)
        if rwc_per_point is not None:
            config['real_world_currency_per_point'] = rwc_per_point
        # need to do this to get SQLAlchemy to detect a change
        session.config = config
        enqueue_admin_message('success', 'Properties have been updated')
        return self.redirect('SessionEditProperties', code=session.code)


class SessionPayments(AdminSessionPage):
    def vars_for_template(self):
        session = self.session
        participants = session.get_participants()
        total_payments = 0.0
        mean_payment = 0.0
        if participants:
            total_payments = sum(
                pp.payoff_plus_participation_fee() for pp in participants
            )
            mean_payment = total_payments / len(participants)

        return dict(
            participants=participants,
            show_finished_status='finished' in settings.PARTICIPANT_FIELDS,
            total_payments=total_payments,
            mean_payment=mean_payment,
            participation_fee=session.config['participation_fee'],
        )


class SessionDataAjax(AdminSessionPage):
    url_pattern = r"/session_data/{code}"

    def get(self, request, code):
        rows = list(export.get_rows_for_data_tab(self.session))
        return JSONResponse(rows)


class SessionData(AdminSessionPage):
    def vars_for_template(self):
        session = self.session

        tables = []
        field_headers = {}
        app_names_by_subsession = []
        round_numbers_by_subsession = []
        for app_name in session.config['app_sequence']:
            models_module = get_models_module(app_name)
            num_rounds = models_module.Subsession.objects_filter(
                session=session
            ).count()
            pfields, gfields, sfields = export.get_fields_for_data_tab(app_name)
            field_headers[app_name] = pfields + gfields + sfields

            for round_number in range(1, num_rounds + 1):
                table = dict(
                    pfields=pfields,
                    gfields=gfields,
                    sfields=sfields,
                )
                tables.append(table)

                app_names_by_subsession.append(app_name)
                round_numbers_by_subsession.append(round_number)
        return dict(
            tables=tables,
            field_headers_json=json.dumps(field_headers),
            app_names_by_subsession=app_names_by_subsession,
            round_numbers_by_subsession=round_numbers_by_subsession,
            DATA_EXPORT_HASH=otree.common.DATA_EXPORT_HASH,
        )


class SessionMonitor(AdminSessionPage):
    def vars_for_template(self):
        field_names = export.get_fields_for_monitor()

        display_names = dict(
            _numeric_label='',
            code='Code',
            label='Label',
            _current_page='Progress',
            _current_app_name='App',
            _round_number='Round',
            _current_page_name='Page name',
            _monitor_note='Waiting for',
            _last_page_timestamp='Time',
        )
        column_names = [display_names[col] for col in field_names]

        return dict(
            column_names=column_names,
            socket_url=channel_utils.session_monitor_path(self.session.code),
            ADVANCE_SLOWEST_BATCH_SIZE=ADVANCE_SLOWEST_BATCH_SIZE,
        )


class SessionDescription(AdminSessionPage):
    def vars_for_template(self):
        return dict(config=SessionConfig(self.session.config))


class AdminReportForm(wtforms.Form):
    app_name = wtforms.SelectField(
        render_kw={'class': 'form-control'},
    )
    # use h5fields to get type='number' (but otree hides the spinner)
    round_number = h5fields.IntegerField(
        validators=[wtvalidators.Optional(), wtvalidators.NumberRange(min=1)],
        render_kw={'autofocus': True, 'class': 'form-control'},
    )

    def __init__(self, *args, session, **kwargs):
        '''we don't validate input it because we don't show the user
        an error. just coerce it to something right'''

        self.session = session
        admin_report_apps = self.session._admin_report_apps()
        num_rounds_list = self.session._admin_report_num_rounds_list()
        self.rounds_per_app = dict(zip(admin_report_apps, num_rounds_list))

        data = kwargs['data']
        # can't use setdefault because the key will always exist even if the
        # fields were empty.
        # str default value is '',
        # and int default value is None
        if not data.get('app_name'):
            data['app_name'] = admin_report_apps[0]
        rounds_in_this_app = self.rounds_per_app[data['app_name']]
        # use 0 so that we can bump it up in the next line
        round_number = int(data.get('round_number', 0))
        if not 1 <= round_number <= rounds_in_this_app:
            data['round_number'] = rounds_in_this_app

        super().__init__(*args, **kwargs)

        app_name_choices = []
        for app_name in admin_report_apps:
            label = f'{app_name} ({self.rounds_per_app[app_name]} rounds)'
            app_name_choices.append((app_name, label))
        self.app_name.choices = app_name_choices


class AdminReport(AdminSessionPage):
    def get_form(self):
        form = AdminReportForm(
            data=dict(self.request.query_params), session=self.session
        )
        form.validate()
        return form

    def get_context_data(self, **kwargs):
        form = kwargs['form']
        app_name = form.app_name.data
        models_module = get_models_module(app_name)
        subsession = models_module.Subsession.objects_get(
            session=self.session, round_number=form.round_number.data
        )

        target = subsession.get_user_defined_target()
        func = getattr(target, 'vars_for_admin_report', None)
        if func:
            vars_for_admin_report = func(subsession)
        else:
            vars_for_admin_report = {}

        self.debug_tables = [
            DebugTable(
                title='vars_for_admin_report', rows=vars_for_admin_report.items()
            )
        ]

        # todo: i think app_label and app_name are the same always
        app_label = subsession.get_folder_name()
        user_template = get_template_name_if_exists(
            [f'{app_label}/admin_report.html', f'{app_label}/AdminReport.html']
        )

        Constants = otree.common.get_constants(app_name)
        context = super().get_context_data(
            subsession=subsession,
            user_template=user_template,
            **kwargs,
        )
        context[Constants.__name__] = Constants
        # it's passed by parent class
        assert 'session' in context

        # this should take priority, in the event of a clash between
        # a user-defined var and a built-in one
        context.update(vars_for_admin_report)
        return context


def get_json_from_pypi() -> dict:
    # import only if we need it
    import urllib.request

    try:
        f = urllib.request.urlopen('https://pypi.python.org/pypi/otree/json', timeout=5)
        return json.loads(f.read().decode('utf-8'))
    except:
        return {'releases': []}


def get_installed_and_pypi_version() -> dict:
    '''return a dict because it needs to be json serialized for the AJAX
    response'''
    # need to import it so it can be patched outside

    semver_re = re.compile(r'^(\d+)\.(\d+)\.(\d+)$')

    installed_dotted = otree.__version__

    data = get_json_from_pypi()

    releases = data['releases']
    newest_tuple = [0, 0, 0]
    newest_dotted = ''
    for release in releases:
        release_match = semver_re.match(release)
        if release_match:
            release_tuple = [int(n) for n in release_match.groups()]
            if release_tuple > newest_tuple:
                newest_tuple = release_tuple
                newest_dotted = release
    return dict(newest=newest_dotted, installed=installed_dotted)


class ServerCheck(AdminView):
    url_pattern = '/server_check'

    def get_context_data(self, **kwargs):
        backend_name = otree.database.engine.url.get_backend_name()
        is_postgres = 'postgres' in backend_name.lower()
        return super().get_context_data(
            debug=settings.DEBUG,
            auth_level=settings.AUTH_LEVEL,
            auth_level_ok=settings.AUTH_LEVEL in {'DEMO', 'STUDY'},
            pypi_results=get_installed_and_pypi_version(),
            is_postgres=is_postgres,
            backend_name=backend_name,
            **kwargs,
        )


class AdvanceSession(AdminView):
    url_pattern = '/AdvanceSession/{code}'

    def post(self, request, code):
        session = db.get_or_404(Session, code=code)
        # background task because it makes http requests,
        # so it will need its own lock.
        session.advance_last_place_participants()
        # task = BackgroundTask(session.advance_last_place_participants)
        return Response('ok')


class Sessions(AdminView):
    url_pattern = '/sessions'

    def vars_for_template(self):
        is_archive = bool(self.request.query_params.get('archived'))
        sessions = (
            Session.objects_filter(is_demo=False, archived=is_archive)
            .order_by(Session.id.desc())
            .all()
        )
        return dict(
            is_archive=is_archive,
            sessions=sessions,
            archived_sessions_exist=Session.objects_exists(archived=True),
        )


class ToggleArchivedSessions(AdminView):
    url_pattern = '/ToggleArchivedSessions'

    def post(self, request):
        post_data = self.get_post_data()
        code_list = post_data.getlist('session')
        for session in Session.objects_filter(Session.code.in_(code_list)):
            session.archived = not session.archived
        return self.redirect('Sessions')


class SaveDB(HTTPEndpoint):
    url_pattern = '/SaveDB'

    def post(self, request):
        import sys
        import os

        # prevent unauthorized requests
        if 'devserver_inner' in sys.argv:
            # very fast, ~0.05s
            save_sqlite_db()
        return Response(str(os.getpid()))


class LoginForm(wtforms.Form):
    username = wtforms.StringField()
    password = wtforms.StringField()

    def validate(self):
        if not super().validate():
            return False

        if (
            self.username.data == settings.ADMIN_USERNAME
            and self.password.data == settings.ADMIN_PASSWORD
        ):
            return True
        self.password.errors.append('Login failed')
        return False


class Login(AdminView):
    url_pattern = '/login'
    form_class = LoginForm

    def vars_for_template(self):
        warnings = []
        for setting in ['ADMIN_USERNAME', 'ADMIN_PASSWORD']:
            if not getattr(settings, setting, None):
                warnings.append(f'{setting} is undefined')
        return dict(warnings=warnings)

    def form_valid(self, form):
        self.request.session[AUTH_COOKIE_NAME] = AUTH_COOKIE_VALUE
        return self.redirect('DemoIndex')


class Logout(HTTPEndpoint):
    url_pattern = '/logout'

    def get(self, request):
        del request.session[AUTH_COOKIE_NAME]
        return RedirectResponse(request.url_for('Login'), status_code=302)


class RedirectToDemo(HTTPEndpoint):
    url_name = '/'

    def get(self, request):
        return RedirectResponse('/demo', status_code=302)
