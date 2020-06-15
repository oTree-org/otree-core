import json
import os
from collections import OrderedDict

from django.views.generic.edit import FormMixin

import otree
import re
import otree.bots.browser
import otree.channels.utils as channel_utils
import otree.common
import otree.export
import otree.models
import vanilla
from django.conf import settings
from django.contrib import messages
from django.urls import reverse
from django.template.loader import select_template
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, redirect
from otree import forms
from otree.currency import RealWorldCurrency
from otree.common import (
    missing_db_tables,
    get_models_module,
    get_app_label_from_name,
    DebugTable,
)
from otree.forms import widgets
from otree.models import Participant, Session
from otree.models_concrete import BrowserBotsLauncherSessionCode, add_time_spent_waiting, RoomsStorage
from otree.session import SESSION_CONFIGS_DICT, create_session, SessionConfig
from otree.views.abstract import AdminSessionPageMixin
from django.db.models import Case, Value, When
from django.http import HttpResponse


class CreateRoomForm(forms.ModelForm):
    name = forms.CharField(required=True, label="", error_messages={"unique": "Dette klassenavn findes allerede. Venligst benyt et andet."},
                           widget=forms.TextInput(attrs={
        'spellcheck': "false",
        "class": "room_name_input",
        'placeholder': "Navngiv dit klasserum"}),
    )

    class Meta:
        model = RoomsStorage
        fields = ["name"]

    def __str__(self):
        return self.name




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
        [('', 'Vælg et spil')]
        + [(s['name'], s['display_name']) for s in session_configs]
    )

    session_config = forms.ChoiceField(choices=session_config_choices, required=True, label="Spil valg")

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
                f'the oTree session will have {settings.MTURK_NUM_PARTICIPANTS_MULTIPLE}'
                '{} times more participant objects than the number you enter here.'
            )
        else:
            self.fields['num_participants'].label = "Antal spillere"

    def clean(self):
        super().clean()
        if self.errors:
            return
        session_config_name = self.cleaned_data['session_config']

        config = SESSION_CONFIGS_DICT[session_config_name]
        lcm = config.get_lcm()
        num_participants = self.cleaned_data.get('num_participants')
        if num_participants is None or num_participants % lcm:
            raise forms.ValidationError('Venligst indtast en valid antal af spillere.')


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


class CreateSessionBadInfluence(FormMixin, vanilla.TemplateView):
    template_name = 'otree/admin/CreateSession.html'
    url_pattern = r"^opret_spil/bad_influence/"
    form_class = CreateSessionForm

    def get_initial(self):
        initial = super().get_initial()
        initial['session_config'] = "bad_influence"
        return initial

    def get_context_data(self, **kwargs):
        x = super().get_context_data(
            configs=SESSION_CONFIGS_DICT.values(),
            **kwargs,
        )

        return x


class CreateSessionDayTrader(FormMixin, vanilla.TemplateView):
    template_name = 'otree/admin/CreateSession.html'
    url_pattern = r"^opret_spil/day_trader/"
    form_class = CreateSessionForm

    def get_initial(self):
        initial = super().get_initial()
        initial['session_config'] = "daytrader"
        return initial

    def get_context_data(self, **kwargs):
        x = super().get_context_data(
            configs=SESSION_CONFIGS_DICT.values(),
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


def link_callback(uri, self):
    # convert URIs to absolute system paths
    if uri.startswith(settings.MEDIA_URL):
        path = os.path.join(settings.MEDIA_ROOT,
                            uri.replace(settings.MEDIA_URL, ""))
    elif uri.startswith(settings.STATIC_URL):
        path = os.path.join(settings.STATIC_ROOT,
                            uri.replace(settings.STATIC_URL, ""))
    else:
        # handle absolute uri
        return uri

    # make sure that file exists
    if not os.path.isfile(path):
        raise Exception(
            "Media URI must start with "
            f"'{settings.STATIC_URL}' or '{settings.MEDIA_URL}'")
    return path


class SessionStartLinks(AdminSessionPageMixin, vanilla.TemplateView):
    def vars_for_template(self):
        session = self.session
        room = session.get_room()

        context = dict(use_browser_bots=session.use_browser_bots)

        session_start_urls = [
            self.request.build_absolute_uri(participant._start_url())
            for participant in session.get_participants()
        ]

        if room:
            context.update(
                participant_urls=room.get_participant_urls(self.request),
                room_wide_url=room.get_room_wide_url(self.request),
                session_start_urls=session_start_urls,
                room=room,
                collapse_links=True,
            )
        else:
            anonymous_url = self.request.build_absolute_uri(
                reverse('JoinSessionAnonymously', args=[session._anonymous_code])
            )

            context.update(
                participant_urls=session_start_urls,
                anonymous_url=anonymous_url,
                num_participants=len(session_start_urls),
                splitscreen_mode_on=len(session_start_urls) <= 3,
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

        self.session.save()
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

        add_time_spent_waiting(participants=participants)

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


class SessionData(AdminSessionPageMixin, vanilla.TemplateView):
    def vars_for_template(self):
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
            columns_for_models, subsession_rows = otree.export.get_rows_for_live_update(
                subsession
            )

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

            round_name = pretty_round_name(
                subsession._meta.app_label, subsession.round_number
            )

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

        return dict(
            subsession_headers=round_headers,
            model_headers=model_headers,
            field_headers=field_names,
            rows=rows,
        )

    def get(self, request, **kwargs):
        context = self.get_context_data()
        if self.request.META.get('CONTENT_TYPE') == 'application/json':
            return JsonResponse(self.context_json, safe=False)
        else:
            return self.render_to_response(context)


class SessionMonitor(AdminSessionPageMixin, vanilla.TemplateView):
    def vars_for_template(self):
        field_names = otree.export.get_field_names_for_live_update(Participant)
        display_names = {
            '_id_in_session': 'Spiller ID',
            'code': 'Kode',
            'label': 'Label',
            '_current_page': 'Side',
            '_current_app_name': 'Spil',
            '_round_number': 'Runde',
            '_current_page_name': 'Side navn',
            'status': 'Status',
            '_last_page_timestamp': 'Tid på siden',
        }

        callable_fields = {'status', '_id_in_session', '_current_page'}

        column_names = [display_names[col] for col in field_names]

        advance_users_button_text = (
            "Advance the slowest user(s) by one page, "
            "by forcing a timeout on their current page. "
        )

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

        page_url_active = {"next_page": "active"}

        return dict(
            column_names=column_names,
            advance_users_button_text=advance_users_button_text,
            page_url_active=page_url_active,
        )

    def get(self, request, *args, **kwargs):
        context = self.get_context_data()
        if self.request.META.get('CONTENT_TYPE') == 'application/json':
            return JsonResponse(self.context_json, safe=False)
        else:
            return self.render_to_response(context)


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
    import urllib.parse

    try:
        f = urllib.request.urlopen('https://pypi.python.org/pypi/otree/json')
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
            sqlite=otree.common.is_sqlite(),
            debug=settings.DEBUG,
            auth_level=settings.AUTH_LEVEL,
            auth_level_ok=settings.AUTH_LEVEL in {'DEMO', 'STUDY'},
            db_synced=not missing_db_tables(),
            pypi_results=get_installed_and_pypi_version(),
            **kwargs,
        )


class CreateBrowserBotsSession(vanilla.View):
    url_pattern = r"^create_browser_bots_session/$"

    def get(self, request, *args, **kwargs):
        return JsonResponse({})

    def post(self, request):
        num_participants = int(request.POST['num_participants'])
        session_config_name = request.POST['session_config_name']
        case_number = int(request.POST['case_number'])
        session = create_session(
            session_config_name=session_config_name, num_participants=num_participants
        )
        otree.bots.browser.initialize_session(
            session_pk=session.pk, case_number=case_number
        )
        BrowserBotsLauncherSessionCode.objects.update_or_create(
            # i don't know why the update_or_create arg is called 'defaults'
            # because it will update even if the instance already exists
            # maybe for consistency with get_or_create
            defaults={'code': session.code}
        )
        channel_utils.sync_group_send_wrapper(
            type='browserbot_sessionready', group='browser_bot_wait', event={}
        )

        return HttpResponse(session.code)


class CloseBrowserBotsSession(vanilla.View):
    url_pattern = r"^close_browser_bots_session/$"

    def post(self, request):
        BrowserBotsLauncherSessionCode.objects.all().delete()
        return HttpResponse('ok')


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


class DeleteSessions(vanilla.View):
    url_pattern = r'^DeleteSessions/'

    def post(self, request):
        Session.objects.filter(code__in=request.POST.getlist('session')).delete()
        return redirect('Sessions')


"""
IKKE SLETTE!
def generate_random_username(length=3, split=7, delimiter='_'):
    game_number = Session.objects.get(id=session.id)
    username = 'Spiller' + ''.join([choice(game_number) for i in range(length)])

    if split:
        username = delimiter.join([username[start:start + split] for start in range(0, len(username), split)])

    try:
        User.objects.get(username=username)
        return generate_random_username(length=length, split=split, delimiter=delimiter)
    except User.DoesNotExist:

        return username
def generate_random_username(length=3, chars=ascii_lowercase, split=7, delimiter='_'):
    username = 'Spiller' + ''.join([choice(chars) for i in range(length)])

    if split:
        username = delimiter.join([username[start:start + split] for start in range(0, len(username), split)])

    try:
        User.objects.get(username=username)
        return generate_random_username(length=length, chars=chars, split=split, delimiter=delimiter)
    except User.DoesNotExist:

        return username
"""

"""
IKKE SLETTE!
- If users exist, then do not create new ones, else create new users for self.session
- Set count = 0, so when we count in the loop, it can increment from 1++
- Create a user for each participant (username)
- Syntax of user is: Spiller<session_id>_1...and upwards depending on number of participants created for the session
- Add a session start url to each user (first_name)
- Add a session.code to each user (last_name)


if User.objects.filter(last_name=self.session.code).exists():
    pass
else:
    count = 0
    admin = User.objects.create_user(username='Admin' + str(session.id), password="123456", is_staff=True,
                                     last_name=session.code)
    admin.save()
    for participant_url in session_start_urls:
        count = count + 1
        user = User.objects.create_user(username='Spiller' + str(session.id) + '_' + str(count),
                                        password="123456", first_name=participant_url, last_name=session.code)
        user.save()
"""
"""
class CreateSessionFormBadInfluence(forms.Form):
    session_configs = SESSION_CONFIGS_DICT.values()
    session_config_choices = (
        [('bad_influence', 'bad_influence')])
    session_config = forms.ChoiceField(choices=session_config_choices, required=True)

    num_participants = forms.IntegerField(required=False,
                                          widget=forms.NumberInput(attrs={'placeholder': 'Indtast antal spillere..'}))
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
                f'the oTree session will have {settings.MTURK_NUM_PARTICIPANTS_MULTIPLE}'
                '{} times more participant objects than the number you enter here.'
            )
        else:
            self.fields['num_participants'].label = "Antal spillere"

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


class CreateSessionFormDayTrader(forms.Form):
    session_configs = SESSION_CONFIGS_DICT.values()
    session_config_choices = (
        [('daytrader', 'daytrader')])
    session_config = forms.ChoiceField(choices=session_config_choices, required=True)

    num_participants = forms.IntegerField(required=False,
                                          widget=forms.NumberInput(attrs={'placeholder': 'Indtast antal spillere..'}))
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
                f'the oTree session will have {settings.MTURK_NUM_PARTICIPANTS_MULTIPLE}'
                '{} times more participant objects than the number you enter here.'
            )
        else:
            self.fields['num_participants'].label = "Antal spillere"

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




"""