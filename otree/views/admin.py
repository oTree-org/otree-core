import json
import os
import sys
from collections import OrderedDict


import channels
import otree.bots.browser
import otree.channels.utils as channel_utils
import otree.common_internal
import otree.export
import otree.models
import vanilla
from django.conf import settings
from django.contrib import messages
from django.urls import reverse
from django.http import HttpResponseRedirect, JsonResponse, HttpResponse, \
    Http404
from django.shortcuts import get_object_or_404
from otree import forms
from otree.common import RealWorldCurrency
from otree.common_internal import (
    create_session_and_redirect, missing_db_tables,
    get_models_module, get_app_label_from_name, DebugTable,
)
from otree.forms import widgets
from otree_startup import check_pypi_for_updates
from otree.models import Participant, Session
from otree.models_concrete import (
    BrowserBotsLauncherSessionCode)
from otree.session import SESSION_CONFIGS_DICT, create_session, SessionConfig
from otree.views.abstract import GenericWaitPageMixin, AdminSessionPageMixin
from django.db.models import Case, Value, When

def pretty_name(name):
    """Converts 'first_name' to 'first name'"""
    if not name:
        return ''
    return name.replace('_', ' ')


class CreateSessionForm(forms.Form):
    session_configs = SESSION_CONFIGS_DICT.values()
    session_config_choices = (
        # use '' instead of None. '' seems to immediately invalidate the choice,
        # rather than None which seems to be coerced to 'None'.
        [('', '-----')] +
        [(s['name'], s['display_name']) for s in session_configs])

    session_config = forms.ChoiceField(
        choices=session_config_choices, required=True)

    num_participants = forms.IntegerField()

    def __init__(self, *args, **kwargs):
        for_mturk = kwargs.pop('for_mturk')
        super().__init__(*args, **kwargs)
        if for_mturk:
            self.fields['num_participants'].label = "Number of MTurk workers"
            self.fields['num_participants'].help_text = (
                'Since workers can return the HIT or drop out, '
                'some "spare" participants will be created: '
                'the oTree session will have '
                '{} times more participants than the MTurk HIT. '
                'The number you enter in this field is number of '
                'workers required for your HIT.'.format(
                    settings.MTURK_NUM_PARTICIPANTS_MULTIPLE
                )
            )
        else:
            self.fields['num_participants'].label = "Number of participants"

    def clean_num_participants(self):
        session_config_name = self.cleaned_data.get('session_config')

        # I think when this is checked, it's possible that basic validation
        # for session_config_name was not done yet.
        # when I tested it was None
        # but maybe it could also be the empty string because that's what's
        # explicitly put above.
        if session_config_name:
            lcm = SESSION_CONFIGS_DICT[session_config_name].get_lcm()
            num_participants = self.cleaned_data['num_participants']
            if num_participants % lcm:
                raise forms.ValidationError(
                    'Please enter a valid number of participants.'
                )
            return num_participants


class CreateSession(vanilla.FormView):
    form_class = CreateSessionForm
    template_name = 'otree/admin/CreateSession.html'

    url_pattern = r"^create_session/$"

    def dispatch(self, request, *args, **kwargs):
        # splinter makes request.GET.get('mturk') == ['1\\']
        # no idea why
        # so just see if it's non-empty
        self.for_mturk = bool(self.request.GET.get('mturk'))
        return super().dispatch(request, *args, **kwargs)

    def get_context_data(self, **kwargs):
        kwargs['configs'] = SESSION_CONFIGS_DICT.values()
        return super().get_context_data(**kwargs)

    def get_form(self, data=None, files=None, **kwargs):
        kwargs['for_mturk'] = self.for_mturk
        return super().get_form(data, files, **kwargs)

    def form_valid(self, form):

        session_config_name = form.cleaned_data['session_config']
        session_kwargs = {
            'session_config_name': session_config_name,
            'for_mturk': self.for_mturk
        }
        if self.for_mturk:
            session_kwargs['num_participants'] = (
                form.cleaned_data['num_participants'] *
                settings.MTURK_NUM_PARTICIPANTS_MULTIPLE
            )

        else:
            session_kwargs['num_participants'] = (
                form.cleaned_data['num_participants'])

        # TODO:
        # Refactor when we upgrade to push
        if hasattr(self, "room"):
            session_kwargs['room_name'] = self.room.name

        post_data = self.request.POST
        config = SESSION_CONFIGS_DICT[session_config_name]

        edited_session_config_fields = {}

        for field in config.editable_fields():
            old_value = config[field]
            html_field_name = config.html_field_name(field)

            # int/float/decimal are set to required in HTML
            # bool:
            # - if unchecked, its key will be missing.
            # - if checked, its value will be 'on'.
            # str:
            # - if blank, its value will be ''
            new_value_str = post_data.get(html_field_name)
            # don't use isinstance because that will catch bool also
            if type(old_value) is int:
                # in case someone enters 1.0 instead of 1
                new_value = int(float(new_value_str))
            else:
                new_value = type(old_value)(new_value_str)
            if old_value != new_value:
                edited_session_config_fields[field] = new_value

        # need to convert to float or string in order to serialize
        # through channels
        for k in ['participation_fee', 'real_world_currency_per_point']:
            if k in edited_session_config_fields:
                edited_session_config_fields[k] = float(
                    edited_session_config_fields[k])
        session_kwargs['edited_session_config_fields'] = edited_session_config_fields


        use_browser_bots = edited_session_config_fields.get('use_browser_bots')
        if use_browser_bots is None:
            use_browser_bots = config.get('use_browser_bots', False)

        return create_session_and_redirect(
            session_kwargs, use_browser_bots=use_browser_bots)


class WaitUntilSessionCreated(GenericWaitPageMixin, vanilla.GenericView):

    url_pattern = r"^WaitUntilSessionCreated/(?P<pre_create_id>.+)/$"

    title_text = 'Creating session'
    body_text = ''

    def _is_ready(self):
        try:
            self.session = Session.objects.get(
                _pre_create_id=self._pre_create_id,
                ready_for_browser=True
            )
            return True
        except Session.DoesNotExist:
            return False

    def _response_when_ready(self):
        session = self.session
        if session.is_for_mturk():
            session_home_url = reverse(
                'MTurkCreateHIT', args=(session.code,)
            )
        # 2017-09-30: deleted a line about split screen here, because
        # the only way to get split screen is to first open the session links
        # page, then switch to split-screen mode
        else:
            session_home_url = reverse(
                'SessionStartLinks', args=(session.code,))

        return HttpResponseRedirect(session_home_url)

    def dispatch(self, request, *args, **kwargs):
        self._pre_create_id = kwargs['pre_create_id']
        if self._is_ready():
            return self._response_when_ready()
        return self._get_wait_page()

    def socket_url(self):
        return channel_utils.wait_for_session_path(self._pre_create_id)


class SessionSplitScreen(AdminSessionPageMixin, vanilla.TemplateView):
    '''Launch the session in fullscreen mode
    only used in demo mode
    '''

    def get_context_data(self, **kwargs):
        '''Get the URLs for the IFrames'''
        context = super(SessionSplitScreen, self).get_context_data(**kwargs)
        participant_urls = [
            self.request.build_absolute_uri(participant._start_url())
            for participant in self.session.get_participants()
        ]
        context.update({
            'session': self.session,
            'participant_urls': participant_urls
        })
        return context


class SessionStartLinks(AdminSessionPageMixin, vanilla.TemplateView):

    def get_context_data(self, **kwargs):
        session = self.session
        room = session.get_room()

        context = super().get_context_data(**kwargs)

        sqlite = settings.DATABASES['default']['ENGINE'].endswith('sqlite3')
        context.update({
            'use_browser_bots': session.use_browser_bots(),
            'sqlite': sqlite,
            'runserver': 'runserver' in sys.argv or 'devserver' in sys.argv
        })

        session_start_urls = [
            self.request.build_absolute_uri(participant._start_url())
            for participant in session.get_participants()
        ]

        # TODO: Bot URLs, and a button to start the bots

        if room:
            context.update(
                {
                    'participant_urls':
                        room.get_participant_urls(self.request),
                    'room_wide_url': room.get_room_wide_url(self.request),
                    'session_start_urls': session_start_urls,
                    'room': room,
                    'collapse_links': True,
                })
        else:
            anonymous_url = self.request.build_absolute_uri(
                reverse(
                    'JoinSessionAnonymously',
                    args=(session._anonymous_code,)
                )
            )

            context.update({
                'participant_urls': session_start_urls,
                'anonymous_url': anonymous_url,
                'num_participants': len(session_start_urls),
                'splitscreen_mode_on': len(session_start_urls) <= 3
            })

        return context


class SessionEditPropertiesForm(forms.ModelForm):
    participation_fee = forms.RealWorldCurrencyField(
        required=False,
        # it seems that if this is omitted, the step defaults to an integer,
        # meaninng fractional inputs are not accepted
        widget=widgets._RealWorldCurrencyInput(attrs={'step': 0.01})
    )
    real_world_currency_per_point = forms.FloatField(
        required=False
    )

    class Meta:
        model = Session
        fields = [
            'label',
            'experimenter_name',
            'comment',
        ]


class SessionEditProperties(AdminSessionPageMixin, vanilla.UpdateView):

    # required for vanilla.UpdateView
    lookup_field = 'code'
    model = Session
    form_class = SessionEditPropertiesForm
    template_name = 'otree/admin/SessionEditProperties.html'

    def get_form(self, data=None, files=None, **kwargs):
        form = super(
            SessionEditProperties, self
        ).get_form(data, files, **kwargs)
        config = self.session.config
        form.fields[
            'participation_fee'
        ].initial = config['participation_fee']
        form.fields[
            'real_world_currency_per_point'
        ].initial = config['real_world_currency_per_point']
        if self.session.mturk_HITId:
            form.fields['participation_fee'].widget.attrs['readonly'] = 'True'
        return form

    def get_success_url(self):
        return reverse('SessionEditProperties', args=(self.session.code,))

    def form_valid(self, form):
        super(SessionEditProperties, self).form_valid(form)
        participation_fee = form.cleaned_data[
            'participation_fee'
        ]
        real_world_currency_per_point = form.cleaned_data[
            'real_world_currency_per_point'
        ]
        config = self.session.config
        if form.cleaned_data['participation_fee'] is not None:
            config[
                'participation_fee'
            # need to convert back to RealWorldCurrency, because easymoney
            # MoneyFormField returns a decimal, not Money (not sure why)
            ] = RealWorldCurrency(participation_fee)
        if form.cleaned_data['real_world_currency_per_point'] is not None:
            config[
                'real_world_currency_per_point'
            ] = real_world_currency_per_point
        self.session.save()
        messages.success(self.request, 'Properties have been updated')
        return HttpResponseRedirect(self.get_success_url())


class SessionPayments(AdminSessionPageMixin, vanilla.TemplateView):

    def get(self, *args, **kwargs):
        response = super(SessionPayments, self).get(*args, **kwargs)
        return response

    def get_context_data(self, **kwargs):
        session = self.session
        # TODO: mark which ones are bots
        participants = session.get_participants()
        total_payments = 0.0
        mean_payment = 0.0
        if participants:
            total_payments = sum(
                part.payoff_plus_participation_fee() for part in participants
            )
            mean_payment = total_payments / len(participants)

        context = super(SessionPayments, self).get_context_data(**kwargs)
        context.update({
            'participants': participants,
            'total_payments': total_payments,
            'mean_payment': mean_payment,
            'participation_fee': session.config['participation_fee'],
        })

        return context


def pretty_round_name(app_label, round_number):
    app_label = pretty_name(app_label)
    if round_number > 1:
        return '{} [Round {}]'.format(app_label, round_number)
    else:
        return app_label


class SessionData(AdminSessionPageMixin, vanilla.TemplateView):

    def get_context_data(self, **kwargs):
        session = self.session

        rows = []

        round_headers = []
        model_headers = []
        field_names = []

        # field names for JSON response
        field_names_json = []

        for subsession in session.get_subsessions():
            # can't use subsession._meta.app_config.name, because it won't work
            # if the app is removed from SESSION_CONFIGS after the session is
            # created.
            columns_for_models, subsession_rows = otree.export.get_rows_for_live_update(subsession)

            if not rows:
                rows = subsession_rows
            else:
                for i in range(len(rows)):
                    rows[i].extend(subsession_rows[i])

            round_colspan = 0
            for model_name in ['player', 'group', 'subsession']:
                colspan = len(columns_for_models[model_name])
                model_headers.append((model_name.title(), colspan))
                round_colspan += colspan

            round_name = pretty_round_name(subsession._meta.app_label, subsession.round_number)

            round_headers.append((round_name, round_colspan))

            this_round_fields = []
            this_round_fields_json = []
            for model_name in ['Player', 'Group', 'Subsession']:
                column_names = columns_for_models[model_name.lower()]
                this_model_fields = [pretty_name(n) for n in column_names]
                this_model_fields_json = [
                    '{}.{}.{}'.format(round_name, model_name, colname)
                    for colname in column_names
                ]
                this_round_fields.extend(this_model_fields)
                this_round_fields_json.extend(this_model_fields_json)

            field_names.extend(this_round_fields)
            field_names_json.extend(this_round_fields_json)

        # dictionary for json response
        # will be used only if json request  is done

        self.context_json = []
        for i, row in enumerate(rows, start=1):
            d_row = OrderedDict()
            # table always starts with participant 1
            d_row['participant_label'] = 'P{}'.format(i)
            for t, v in zip(field_names_json, row):
                d_row[t] = v
            self.context_json.append(d_row)

        context = super().get_context_data(**kwargs)
        context.update({
            'subsession_headers': round_headers,
            'model_headers': model_headers,
            'field_headers': field_names,
            'rows': rows})
        return context

    def get(self, request, *args, **kwargs):
        context = self.get_context_data()
        if self.request.META.get('CONTENT_TYPE') == 'application/json':
            return JsonResponse(self.context_json, safe=False)
        else:
            return self.render_to_response(context)


class SessionMonitor(AdminSessionPageMixin, vanilla.TemplateView):

    def get_context_data(self, **kwargs):

        field_names = otree.export.get_field_names_for_live_update(Participant)
        display_names = {
            '_id_in_session': 'ID in session',
            'code': 'Code',
            'label': 'Label',
            '_current_page': 'Page',
            '_current_app_name': 'App',
            '_round_number': 'Round',
            '_current_page_name': 'Page name',
            'status': 'Status',
            '_last_page_timestamp': 'Time on page',
        }

        callable_fields = {'status', '_id_in_session', '_current_page'}

        column_names = [display_names[col] for col in field_names]

        context = super().get_context_data(**kwargs)
        context['column_names'] = column_names

        advance_users_button_text = (
            "Advance the slowest user(s) by one page, "
            "by forcing a timeout on their current page. "
        )
        context['advance_users_button_text'] = advance_users_button_text


        participants = self.session.participant_set.filter(visited=True)
        rows = []

        for participant in participants:
            row = {}
            for field_name in field_names:
                value = getattr(participant, field_name)
                if field_name in callable_fields:
                    value = value()
                row[field_name] = value
            rows.append(row)

        self.context_json = rows

        return context

    def get(self, request, *args, **kwargs):
        context = self.get_context_data()
        if self.request.META.get('CONTENT_TYPE') == 'application/json':
            return JsonResponse(self.context_json, safe=False)
        else:
            return self.render_to_response(context)



class SessionDescription(AdminSessionPageMixin, vanilla.TemplateView):

    def get_context_data(self, **kwargs):
        context = super(SessionDescription, self).get_context_data(**kwargs)
        context['config'] = SessionConfig(self.session.config)
        return context


class AdminReportForm(forms.Form):
    app_name = forms.ChoiceField(choices=[], required=False)
    round_number = forms.IntegerField(required=False, min_value=1)

    def __init__(self, *args, **kwargs):
        self.session = kwargs.pop('session')
        super().__init__(*args, **kwargs)

        admin_report_apps = self.session._admin_report_apps()
        num_rounds_list = self.session._admin_report_num_rounds_list()
        self.rounds_per_app = dict(zip(admin_report_apps, num_rounds_list))
        app_name_choices = []
        for app_name in admin_report_apps:
            label = '{} ({} rounds)'.format(
                get_app_label_from_name(app_name), self.rounds_per_app[app_name]
            )
            app_name_choices.append((app_name, label))

        self.fields['app_name'].choices = app_name_choices

    def clean(self):
        cleaned_data = super().clean()

        apps_with_admin_report = self.session._admin_report_apps()

        # can't use setdefault because the key will always exist even if the
        # fields were empty.
        # str default value is '',
        # and int default value is None
        if not cleaned_data['app_name']:
            cleaned_data['app_name'] = apps_with_admin_report[0]

        rounds_in_this_app = self.rounds_per_app[cleaned_data['app_name']]

        round_number = cleaned_data['round_number']

        if not round_number or round_number > rounds_in_this_app:
            cleaned_data['round_number'] = rounds_in_this_app

        self.data = cleaned_data

        return cleaned_data


class AdminReport(AdminSessionPageMixin, vanilla.TemplateView):

    def get(self, request, *args, **kwargs):
        form = AdminReportForm(data=request.GET, session=self.session)
        # validate to get error messages
        form.is_valid()
        context = self.get_context_data(form=form)
        return self.render_to_response(context)

    def get_context_data(self, **kwargs):

        cleaned_data = kwargs['form'].cleaned_data

        models_module = get_models_module(cleaned_data['app_name'])
        subsession = models_module.Subsession.objects.get(
            session=self.session,
            round_number=cleaned_data['round_number'],
        )

        context = {
            'subsession': subsession,
            'Constants': models_module.Constants,
            'session': self.session,
            'user_template': '{}/AdminReport.html'.format(
            subsession._meta.app_config.label)
        }

        vars_for_admin_report = subsession.vars_for_admin_report() or {}
        self.debug_tables = [
            DebugTable(
                title='vars_for_admin_report',
                rows=vars_for_admin_report.items()
            )
        ]
        # determine whether to display debug tables
        self.is_debug = settings.DEBUG
        context.update(vars_for_admin_report)

        # this should take priority, in the event of a clash between
        # a user-defined var and a built-in one
        context.update(super().get_context_data(**kwargs))



        return context


class ServerCheck(vanilla.TemplateView):
    template_name = 'otree/admin/ServerCheck.html'

    url_pattern = r"^server_check/$"

    def app_is_on_heroku(self):
        return 'heroku' in self.request.get_host()

    def worker_is_running(self):
        if otree.common_internal.USE_REDIS:
            redis_conn = otree.common_internal.get_redis_conn()
            return otree.bots.browser.ping_bool(redis_conn, timeout=2)
        else:
            # the timeoutworker relies on Redis (Huey),
            # so if Redis is not being used, the timeoutworker is not functional
            return False

    def get_context_data(self, **kwargs):
        sqlite = settings.DATABASES['default']['ENGINE'].endswith('sqlite3')
        debug = settings.DEBUG
        regular_sentry = hasattr(settings, 'RAVEN_CONFIG')
        heroku_sentry = os.environ.get('SENTRY_DSN')
        sentry = regular_sentry or heroku_sentry
        auth_level = settings.AUTH_LEVEL
        auth_level_ok = settings.AUTH_LEVEL in {'DEMO', 'STUDY'}
        heroku = self.app_is_on_heroku()
        runserver = ('runserver' in sys.argv) or ('devserver' in sys.argv)
        db_synced = not missing_db_tables()
        pypi_results = check_pypi_for_updates()
        worker_is_running = self.worker_is_running()

        return {
            'sqlite': sqlite,
            'debug': debug,
            'sentry': sentry,
            'auth_level': auth_level,
            'auth_level_ok': auth_level_ok,
            'heroku': heroku,
            'runserver': runserver,
            'db_synced': db_synced,
            'pypi_results': pypi_results,
            'worker_is_running': worker_is_running,
        }


class OtreeCoreUpdateCheck(vanilla.View):

    url_pattern = r"^version_cached/$"

    # cached per process
    results = None

    def get(self, request, *args, **kwargs):
        if OtreeCoreUpdateCheck.results is None:
            OtreeCoreUpdateCheck.results = check_pypi_for_updates()
        return JsonResponse(OtreeCoreUpdateCheck.results, safe=True)


class CreateBrowserBotsSession(vanilla.View):

    url_pattern = r"^create_browser_bots_session/$"

    def get(self, request, *args, **kwargs):
        # return browser bots check
        sqlite = settings.DATABASES['default']['ENGINE'].endswith('sqlite3')

        return JsonResponse({
            'sqlite': sqlite,
            'runserver': 'runserver' in sys.argv or 'devserver' in sys.argv
        })

    def post(self, request, *args, **kwargs):
        num_participants = int(request.POST['num_participants'])
        session_config_name = request.POST['session_config_name']
        case_number = int(request.POST['case_number'])
        session = create_session(
            session_config_name=session_config_name,
            num_participants=num_participants,
        )
        otree.bots.browser.initialize_session(
            session_pk=session.pk, case_number=case_number)
        BrowserBotsLauncherSessionCode.objects.update_or_create(
            # i don't know why the update_or_create arg is called 'defaults'
            # because it will update even if the instance already exists
            # maybe for consistency with get_or_create
            defaults={'code': session.code}
        )
        channels.Group('browser_bot_wait').send(
            {'text': json.dumps({'status': 'session_ready'})}
        )

        return HttpResponse(session.code)


class CloseBrowserBotsSession(vanilla.View):

    url_pattern = r"^close_browser_bots_session/$"

    def post(self, request, *args, **kwargs):
        BrowserBotsLauncherSessionCode.objects.all().delete()
        return HttpResponse('ok')


class AdvanceSession(vanilla.View):

    url_pattern = r'^AdvanceSession/(?P<session_code>[a-z0-9]+)/$'

    def post(self, *args, **kwargs):
        session = get_object_or_404(
            otree.models.Session, code=kwargs['session_code']
        )
        session.advance_last_place_participants()
        return HttpResponse('ok')


class Sessions(vanilla.ListView):
    template_name = 'otree/admin/Sessions.html'

    url_pattern = r"^sessions/$"

    def dispatch(self, request, *args, **kwargs):
        self.is_archive = self.request.GET.get('archived') == '1'
        return super().dispatch(request, *args, **kwargs)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        archived_sessions_exist = Session.objects.filter(archived=True).exists()
        context.update({
            'is_archive': self.is_archive,
            'is_debug': settings.DEBUG,
            'archived_sessions_exist': archived_sessions_exist
        })
        return context

    def get_queryset(self):
        return Session.objects.filter(
            is_demo=False, archived=self.is_archive).order_by('-pk')


class ToggleArchivedSessions(vanilla.View):

    url_pattern = r'^ToggleArchivedSessions/'

    def post(self, request, *args, **kwargs):
        code_list = request.POST.getlist('session')

        (Session.objects.filter(code__in=code_list)
            .update(archived=Case(
                When(archived=True, then=Value(False)),
                default=Value(True))
            )
        )

        return HttpResponseRedirect(reverse('Sessions'))


class DeleteSessions(vanilla.View):

    url_pattern = r'^DeleteSessions/'

    def dispatch(self, *args, **kwargs):
        return super(DeleteSessions, self).dispatch(*args, **kwargs)

    def post(self, request, *args, **kwargs):
        for code in request.POST.getlist('session'):
            session = get_object_or_404(
                otree.models.Session, code=code
            )
            session.delete()
        return HttpResponseRedirect(reverse('Sessions'))