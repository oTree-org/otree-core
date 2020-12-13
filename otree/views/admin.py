import json
import logging
import re
import vanilla
from django.conf import settings
from django.contrib import messages
from django.db.models import Case, Value, When
from django.http import JsonResponse, HttpResponse
from django.shortcuts import get_object_or_404, redirect
from django.template.loader import select_template
from django.urls import reverse
from django.utils.decorators import method_decorator
from django.views.decorators.csrf import csrf_exempt
from django.forms import widgets as dj_widgets

import otree
import otree.bots.browser
import otree.channels.utils as channel_utils
import otree.common
from otree import export
import otree.models
from otree import forms, tasks
from otree.common import (
    missing_db_tables,
    get_models_module,
    get_app_label_from_name,
    DebugTable,
)
from otree.currency import RealWorldCurrency
from otree.forms import widgets
from otree.models import Participant, Session
from otree.session import SESSION_CONFIGS_DICT, SessionConfig
from otree.views.abstract import AdminSessionPageMixin


def pretty_name(name):
    """Converts 'first_name' to 'first name'"""
    if not name:
        return ''
    return name.replace('_', ' ')


class CreateSessionForm(forms.Form):
    session_configs = SESSION_CONFIGS_DICT.values()
    session_config_choices = [(s['name'], s['display_name']) for s in session_configs]

    session_config = forms.ChoiceField(
        choices=session_config_choices,
        required=True,
        widget=dj_widgets.Select(attrs=dict(autofocus='autofocus')),
    )

    num_participants = forms.IntegerField(required=False)
    is_mturk = forms.BooleanField(
        widget=widgets.HiddenInput, initial=False, required=False
    )
    room_name = forms.CharField(
        initial=None, widget=widgets.HiddenInput, required=False
    )

    def __init__(self, *args, is_mturk=False, room_name=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['room_name'].initial = room_name
        if is_mturk:
            self.fields['is_mturk'].initial = True
            self.fields[
                'num_participants'
            ].label = "Number of MTurk workers (assignments)"
            self.fields['num_participants'].help_text = (
                'Since workers can return an assignment or drop out, '
                'some "spare" participants will be created: '
                f'the oTree session will have {settings.MTURK_NUM_PARTICIPANTS_MULTIPLE} '
                'times more participant objects than the number you enter here.'
            )
        else:
            self.fields['num_participants'].label = "Number of participants"

    def clean(self):
        super().clean()
        if self.errors:
            return
        session_config_name = self.cleaned_data['session_config']

        config = SESSION_CONFIGS_DICT[session_config_name]
        lcm = config.get_lcm()
        num_participants = self.cleaned_data.get('num_participants')
        if num_participants is None or num_participants % lcm:
            raise forms.ValidationError('Please enter a valid number of participants.')


class CreateSession(vanilla.TemplateView):
    template_name = 'otree/admin/CreateSession.html'
    url_pattern = r"^create_session/$"

    def get_context_data(self, **kwargs):
        x = super().get_context_data(
            configs=SESSION_CONFIGS_DICT.values(),
            # splinter makes request.GET.get('mturk') == ['1\\']
            # no idea why
            # so just see if it's non-empty
            form=CreateSessionForm(is_mturk=bool(self.request.GET.get('is_mturk'))),
            **kwargs,
        )
        return x


class SessionSplitScreen(AdminSessionPageMixin, vanilla.TemplateView):
    '''Launch the session in fullscreen mode
    only used in demo mode
    '''

    def vars_for_template(self):
        '''Get the URLs for the IFrames'''
        participant_urls = [
            self.request.build_absolute_uri(participant._start_url())
            for participant in self.session.get_participants()
        ]
        return dict(session=self.session, participant_urls=participant_urls)


class SessionStartLinks(AdminSessionPageMixin, vanilla.TemplateView):
    def vars_for_template(self):
        session = self.session
        room = session.get_room()

        p_codes = session.participant_set.order_by('id_in_session').values_list(
            'code', flat=True
        )
        participant_urls = []
        for code in p_codes:
            rel_url = otree.common.participant_start_url(code)
            url = self.request.build_absolute_uri(rel_url)
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
            anonymous_url = self.request.build_absolute_uri(
                reverse('JoinSessionAnonymously', args=[session._anonymous_code])
            )

            context.update(
                anonymous_url=anonymous_url,
                num_participants=len(participant_urls),
                splitscreen_mode_on=len(participant_urls) <= 3,
            )

        return context


class SessionEditPropertiesForm(forms.Form):
    participation_fee = forms.RealWorldCurrencyField(
        required=False,
        # it seems that if this is omitted, the step defaults to an integer,
        # meaninng fractional inputs are not accepted
        widget=widgets._RealWorldCurrencyInput(attrs={'step': 0.01}),
    )
    real_world_currency_per_point = forms.FloatField(required=False)

    label = forms.CharField(required=False)
    comment = forms.CharField(required=False)


class SessionEditProperties(AdminSessionPageMixin, vanilla.FormView):
    form_class = SessionEditPropertiesForm
    template_name = 'otree/admin/SessionEditProperties.html'

    def get_form(self, data=None, files=None, **kwargs):
        form = super().get_form(data, files, **kwargs)
        session = self.session
        config = session.config
        fields = form.fields
        fields['participation_fee'].initial = config['participation_fee']
        fields['real_world_currency_per_point'].initial = config[
            'real_world_currency_per_point'
        ]
        fields['label'].initial = session.label
        fields['comment'].initial = session.comment
        if session.mturk_HITId:
            fields['participation_fee'].widget.attrs['readonly'] = 'True'
        return form

    def form_valid(self, form):
        session = self.session
        session.label = form.cleaned_data['label']
        session.comment = form.cleaned_data['comment']

        participation_fee = form.cleaned_data['participation_fee']
        rwc_per_point = form.cleaned_data['real_world_currency_per_point']

        if participation_fee is not None:
            # need to convert back to RealWorldCurrency, because easymoney
            # MoneyFormField returns a decimal, not Money (not sure why)
            session.config['participation_fee'] = RealWorldCurrency(participation_fee)
        if rwc_per_point is not None:
            session.config['real_world_currency_per_point'] = rwc_per_point

        # ensure config gets saved because usually it doesn't
        self.session.save(update_fields=['config', 'label', 'comment'])
        messages.success(self.request, 'Properties have been updated')
        return redirect('SessionEditProperties', session.code)


class SessionPayments(AdminSessionPageMixin, vanilla.TemplateView):
    def vars_for_template(self):
        session = self.session
        participants = session.get_participants()
        total_payments = 0.0
        mean_payment = 0.0
        if participants:
            total_payments = sum(
                part.payoff_plus_participation_fee() for part in participants
            )
            mean_payment = total_payments / len(participants)

        return dict(
            participants=participants,
            total_payments=total_payments,
            mean_payment=mean_payment,
            participation_fee=session.config['participation_fee'],
        )


def pretty_round_name(app_label, round_number):
    app_label = pretty_name(app_label)
    if round_number > 1:
        return '{} [Round {}]'.format(app_label, round_number)
    else:
        return app_label


class SessionDataAjax(vanilla.View):
    url_pattern = r"^session_data/(?P<code>[a-z0-9]+)/$"

    def get(self, request, code):
        session = get_object_or_404(Session, code=code)
        rows = list(export.get_rows_for_data_tab(session))
        return JsonResponse(rows, safe=False)


class SessionData(AdminSessionPageMixin, vanilla.TemplateView):
    def vars_for_template(self):
        session = self.session

        tables = []
        field_headers = {}
        app_names_by_subsession = []
        round_numbers_by_subsession = []
        for app_name in session.config['app_sequence']:
            models_module = get_models_module(app_name)
            num_rounds = models_module.Subsession.objects.filter(
                session=session
            ).count()
            pfields, gfields, sfields = export.get_fields_for_data_tab(app_name)
            field_headers[app_name] = pfields + gfields + sfields

            for round_number in range(1, num_rounds + 1):
                table = dict(pfields=pfields, gfields=gfields, sfields=sfields,)
                tables.append(table)

                app_names_by_subsession.append(app_name)
                round_numbers_by_subsession.append(round_number)
        return dict(
            tables=tables,
            field_headers_json=json.dumps(field_headers),
            app_names_by_subsession=app_names_by_subsession,
            round_numbers_by_subsession=round_numbers_by_subsession,
        )


class SessionMonitor(AdminSessionPageMixin, vanilla.TemplateView):
    def get_context_data(self, **kwargs):
        field_names = export.get_fields_for_monitor()

        display_names = {
            '_numeric_label': '',
            'code': 'Code',
            'label': 'Label',
            '_current_page': 'Progress',
            '_current_app_name': 'App',
            '_round_number': 'Round',
            '_current_page_name': 'Page name',
            '_monitor_note': 'Waiting for',
            '_last_page_timestamp': 'Time',
        }
        column_names = [display_names[col] for col in field_names]

        return super().get_context_data(
            column_names=column_names,
            socket_url=channel_utils.session_monitor_path(self.session.code),
        )


class SessionDescription(AdminSessionPageMixin, vanilla.TemplateView):
    def vars_for_template(self):
        return dict(config=SessionConfig(self.session.config))


class AdminReportForm(forms.Form):
    app_name = forms.ChoiceField(choices=[], required=False)
    round_number = forms.IntegerField(required=False, min_value=1)

    def __init__(self, *args, session, **kwargs):
        self.session = session
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
            session=self.session, round_number=cleaned_data['round_number']
        )

        vars_for_admin_report = subsession.vars_for_admin_report() or {}
        self.debug_tables = [
            DebugTable(
                title='vars_for_admin_report', rows=vars_for_admin_report.items()
            )
        ]
        # determine whether to display debug tables
        self.is_debug = settings.DEBUG

        app_label = subsession._meta.app_config.label
        user_template = select_template(
            [f'{app_label}/admin_report.html', f'{app_label}/AdminReport.html']
        )

        context = super().get_context_data(
            subsession=subsession,
            Constants=models_module.Constants,
            user_template=user_template,
            **kwargs,
        )
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


class ServerCheck(vanilla.TemplateView):
    template_name = 'otree/admin/ServerCheck.html'

    url_pattern = r"^server_check/$"

    def get_context_data(self, **kwargs):
        return super().get_context_data(
            debug=settings.DEBUG,
            auth_level=settings.AUTH_LEVEL,
            auth_level_ok=settings.AUTH_LEVEL in {'DEMO', 'STUDY'},
            db_synced=not missing_db_tables(),
            pypi_results=get_installed_and_pypi_version(),
            **kwargs,
        )


class AdvanceSession(vanilla.View):
    url_pattern = r'^AdvanceSession/(?P<session_code>[a-z0-9]+)/$'

    def post(self, request, session_code):
        session = get_object_or_404(otree.models.Session, code=session_code)
        session.advance_last_place_participants()
        return HttpResponse('ok')


class Sessions(vanilla.ListView):
    template_name = 'otree/admin/Sessions.html'

    url_pattern = r"^sessions/$"

    def dispatch(self, request):
        self.is_archive = self.request.GET.get('archived') == '1'
        return super().dispatch(request)

    def get_context_data(self, **kwargs):
        return super().get_context_data(
            is_archive=self.is_archive,
            is_debug=settings.DEBUG,
            archived_sessions_exist=Session.objects.filter(archived=True).exists(),
            **kwargs,
        )

    def get_queryset(self):
        return Session.objects.filter(is_demo=False, archived=self.is_archive).order_by(
            '-pk'
        )


class ToggleArchivedSessions(vanilla.View):
    url_pattern = r'^ToggleArchivedSessions/'

    def post(self, request):
        code_list = request.POST.getlist('session')

        (
            Session.objects.filter(code__in=code_list).update(
                archived=Case(
                    When(archived=True, then=Value(False)), default=Value(True)
                )
            )
        )

        return redirect('Sessions')


@method_decorator(csrf_exempt, name='dispatch')
class SaveDB(vanilla.View):
    url_pattern = r'^SaveDB/'

    def post(self, request):
        import sys
        import os
        from otree.common import dump_db

        # prevent unauthorized requests
        if 'devserver_inner' in sys.argv:
            # very fast, ~0.05s
            dump_db()
        return HttpResponse(str(os.getpid()))
