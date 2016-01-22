#!/usr/bin/env python
# -*- coding: utf-8 -*-

import collections
import threading
import time
import uuid
import itertools
from six.moves import range
from six.moves.urllib.parse import unquote_plus
from six.moves.urllib.parse import urlencode
from six.moves import zip

from django.template.response import TemplateResponse
from django.http import HttpResponseRedirect, JsonResponse
from django.core.urlresolvers import reverse
from django.forms.forms import pretty_name
from django.conf import settings
from django.contrib import messages
from django.utils.encoding import force_text

import vanilla

from ordered_set import OrderedSet as oset
from collections import OrderedDict

import easymoney

from otree.common_internal import (
    get_models_module, app_name_format, add_params_to_url
)
from otree.session import (
    create_session, get_session_configs_dict, get_session_configs_list,
    get_lcm
)
from otree import forms
from otree.common import RealWorldCurrency
from otree.views.abstract import GenericWaitPageMixin, AdminSessionPageMixin
from otree.views.mturk import MTurkConnection

import otree.constants_internal
import otree.models.session
from otree.common import Currency as c
from otree.models.session import Session
from otree.models.participant import Participant
from otree.models.session import GlobalSingleton
from otree.models_concrete import PageCompletion


def get_all_fields(Model, for_export=False):

    if Model is PageCompletion:
        return [
            'session_pk',
            'participant_pk',
            'page_index',
            'app_name',
            'page_name',
            'time_stamp',
            'seconds_on_page',
            'subsession_pk',
        ]

    if Model is Session:
        return [
            'code',
            'label',
            'experimenter_name',
            'real_world_currency_per_point',
            'time_scheduled',
            'time_started',
            'mturk_HITId',
            'mturk_HITGroupId',
            'participation_fee',
            'comment',
            'special_category',
        ]

    if Model is Participant:
        if for_export:
            return [
                '_id_in_session',
                'code',
                'label',
                '_current_page',
                '_current_app_name',
                '_round_number',
                '_current_page_name',
                'status',
                'last_request_succeeded',
                'ip_address',
                'time_started',
                'exclude_from_data_analysis',
                'name',
                'session',
                'visited',
                'mturk_worker_id',
                'mturk_assignment_id',
            ]
        else:
            return [
                '_id_in_session',
                'code',
                'label',
                '_current_page',
                '_current_app_name',
                '_round_number',
                '_current_page_name',
                'status',
                'last_request_succeeded',
                '_last_page_timestamp',
            ]

    first_fields = {
        'Player':
            [
                'id_in_group',
                'role',
            ],
        'Group':
            [
                'id',
            ],
        'Subsession':
            [],
    }[Model.__name__]
    first_fields = oset(first_fields)

    last_fields = {
        'Player': [],
        'Group': [],
        'Subsession': [],
    }[Model.__name__]
    last_fields = oset(last_fields)

    fields_for_export_but_not_view = {
        'Player': {'id', 'label', 'subsession', 'session'},
        'Group': {'id'},
        'Subsession': {'id', 'round_number'},
    }[Model.__name__]

    fields_for_view_but_not_export = {
        'Player': set(),
        'Group': {'subsession', 'session'},
        'Subsession': {'session'},
    }[Model.__name__]

    fields_to_exclude_from_export_and_view = {
        'Player': {
            '_index_in_game_pages',
            'participant',
            'group',
            'subsession',
            'session',
            'round_number',
        },
        'Group': {
            'subsession',
            'id_in_subsession',
            'session',
            '_is_missing_players',
            'round_number',
        },
        'Subsession': {
            'code',
            'label',
            'session',
            'session_access_code',
        },
    }[Model.__name__]

    if for_export:
        fields_to_exclude = fields_to_exclude_from_export_and_view.union(
            fields_for_view_but_not_export
        )
    else:
        fields_to_exclude = fields_to_exclude_from_export_and_view.union(
            fields_for_export_but_not_view
        )

    all_fields_in_model = oset([field.name for field in Model._meta.fields])

    middle_fields = (
        all_fields_in_model - first_fields - last_fields - fields_to_exclude
    )

    return list(first_fields | middle_fields | last_fields)


def get_display_table_rows(app_name, for_export, subsession_pk=None):
    if not for_export and not subsession_pk:
        raise ValueError("if this is for the admin results table, "
                         "you need to specify a subsession pk")
    models_module = otree.common_internal.get_models_module(app_name)
    Player = models_module.Player
    Group = models_module.Group
    Subsession = models_module.Subsession
    if for_export:
        model_order = [
            Participant,
            Player,
            Group,
            Subsession,
            Session
        ]
    else:
        model_order = [
            Player,
            Group,
            Subsession,
        ]

    # get title row
    all_columns = []
    for Model in model_order:
        field_names = get_all_fields(Model, for_export)
        columns_for_this_model = [
            (Model, field_name) for field_name in field_names
        ]
        all_columns.extend(columns_for_this_model)

    if subsession_pk:
        # we had a strange result on one person's heroku instance
        # where Meta.ordering on the Player was being ingnored
        # when you use a filter. So we add one explicitly.
        players = Player.objects.filter(
            subsession_id=subsession_pk).order_by('pk')
    else:
        players = Player.objects.all()
    session_ids = set([player.session_id for player in players])

    # initialize
    parent_objects = {}

    parent_models = [
        Model for Model in model_order if Model not in {Player, Session}
    ]

    for Model in parent_models:
        parent_objects[Model] = {
            obj.pk: obj
            for obj in Model.objects.filter(session_id__in=session_ids)
        }

    if Session in model_order:
        parent_objects[Session] = {
            obj.pk: obj for obj in Session.objects.filter(pk__in=session_ids)
        }

    all_rows = []
    for player in players:
        row = []
        for column in all_columns:
            Model, field_name = column
            if Model == Player:
                model_instance = player
            else:
                fk_name = Model.__name__.lower()
                parent_object_id = getattr(player, "{}_id".format(fk_name))
                if parent_object_id is None:
                    model_instance = None
                else:
                    model_instance = parent_objects[Model][parent_object_id]

            attr = getattr(model_instance, field_name, '')
            if isinstance(attr, collections.Callable):
                if Model == Player and field_name == 'role' \
                        and model_instance.group is None:
                    attr = ''
                else:
                    try:
                        attr = attr()
                    except:
                        attr = "(error)"
            row.append(attr)
        all_rows.append(row)

    values_to_replace = {None: '', True: 1, False: 0}

    for row in all_rows:
        for i in range(len(row)):
            value = row[i]
            try:
                replace = value in values_to_replace
            except TypeError:
                # if it's an unhashable data type
                # like Json or Pickle field
                replace = False
            if replace:
                value = values_to_replace[value]
            elif for_export and isinstance(value, easymoney.Money):
                # remove currency formatting for easier analysis
                value = easymoney.to_dec(value)
            value = force_text(value)
            value = value.replace('\n', ' ').replace('\r', ' ')
            row[i] = value

    column_display_names = []
    for Model, field_name in all_columns:
        column_display_names.append(
            (Model.__name__, field_name)
        )

    return column_display_names, all_rows


class PersistentLabURLs(vanilla.TemplateView):

    @classmethod
    def url_pattern(cls):
        return r"^persistent_lab_urls/$"

    @classmethod
    def url_name(cls):
        return 'persistent_lab_urls'

    template_name = 'otree/admin/PersistentLabURLs.html'

    def get_context_data(self, **kwargs):
        context = super(PersistentLabURLs, self).get_context_data(**kwargs)

        # default session stuff
        default_session_base_url = self.request.build_absolute_uri(
            reverse('assign_visitor_to_default_session')
        )
        default_session_example_urls = []
        for i in range(1, 20):
            data_urls = add_params_to_url(
                default_session_base_url,
                {
                    'participant_label': 'PC-{}'.format(i),
                    'access_code_for_default_session':
                    settings.ACCESS_CODE_FOR_DEFAULT_SESSION
                }
            )
            default_session_example_urls.append(data_urls)
        global_singleton = GlobalSingleton.objects.get()
        default_session = global_singleton.default_session

        context.update({
            'default_session_example_urls': default_session_example_urls,
            'access_code_for_default_session': (
                otree.constants_internal.access_code_for_default_session
            ),
            'participant_label': otree.constants_internal.participant_label,
            'default_session': default_session,
        })
        return context


class CreateSessionForm(forms.Form):

    num_participants = forms.IntegerField()

    def __init__(self, *args, **kwargs):
        self.session_config = kwargs.pop('session_config')
        for_mturk = kwargs.pop('for_mturk')
        super(CreateSessionForm, self).__init__(*args, **kwargs)
        if for_mturk:
            self.fields['num_participants'].label = "Number of workers"
            self.fields['num_participants'].help_text = (
                'Since workers can return the hit or drop out '
                '"spare" participants will be created. Namely server will '
                'have %s times more participants than MTurk HIT. '
                'The number you enter in this field is number of '
                'workers required for your HIT.'
                % settings.MTURK_NUM_PARTICIPANTS_MULT
            )
        else:
            self.fields['num_participants'].label = "Number of participants"

    def clean_num_participants(self):

        lcm = get_lcm(self.session_config)
        num_participants = self.cleaned_data['num_participants']
        if num_participants % lcm:
            raise forms.ValidationError(
                'Number of participants must be a multiple of {}'.format(lcm)
            )
        return num_participants


class WaitUntilSessionCreated(GenericWaitPageMixin, vanilla.GenericView):

    @classmethod
    def url_pattern(cls):
        return r"^WaitUntilSessionCreated/(?P<session_pre_create_id>.+)/$"

    @classmethod
    def url_name(cls):
        return 'wait_until_session_created'

    def _is_ready(self):
        thread_create_session = None
        for t in threading.enumerate():
            if t.name == self._pre_create_id:
                thread_create_session = t
        thread_alive = (
            thread_create_session and
            thread_create_session.isAlive()
        )
        session_exists = Session.objects.filter(
            _pre_create_id=self._pre_create_id
        ).exists()

        if not thread_alive and not session_exists:
            raise Exception("Thread failed to create new session")
        return session_exists

    def body_text(self):
        return 'Waiting until session created'

    def _response_when_ready(self):
        session = Session.objects.get(_pre_create_id=self._pre_create_id)
        if self.request.session.get('for_mturk', False):
            session.mturk_num_participants = (
                len(session.get_participants()) /
                settings.MTURK_NUM_PARTICIPANTS_MULT
            )
        session.save()
        if session.is_for_mturk():
            session_home_url = reverse(
                'session_create_hit', args=(session.pk,)
            )
        else:
            session_home_url = reverse(
                'session_start_links', args=(session.pk,)
            )
        return HttpResponseRedirect(session_home_url)

    def dispatch(self, request, *args, **kwargs):
        self._pre_create_id = kwargs['session_pre_create_id']
        return super(WaitUntilSessionCreated, self).dispatch(
            request, *args, **kwargs
        )


def sleep_then_create_session(**kwargs):

    # hack: this sleep is to prevent locks on SQLite. This gives time to let
    # the page request finish before create_session is called,
    # because creating the session involves a lot of database I/O, which seems
    # to cause locks when multiple threads access at the same time.
    if settings.DATABASES['default']['ENGINE'].endswith('sqlite3'):
        time.sleep(5)

    create_session(**kwargs)


class CreateSession(vanilla.FormView):

    form_class = CreateSessionForm
    template_name = 'otree/admin/CreateSession.html'

    @classmethod
    def url_pattern(cls):
        return r"^create_session/(?P<session_config>.+)/$"

    @classmethod
    def url_name(cls):
        return 'session_create'

    def dispatch(self, request, *args, **kwargs):
        session_config_name = unquote_plus(kwargs.pop('session_config'))
        self.session_config = get_session_configs_dict()[session_config_name]
        self.for_mturk = (int(self.request.GET.get('mturk', 0)) == 1)
        return super(CreateSession, self).dispatch(request, *args, **kwargs)

    def get_context_data(self, **kwargs):
        context = info_about_session_config(self.session_config)
        kwargs.update(context)
        return super(CreateSession, self).get_context_data(**kwargs)

    def get_form(self, data=None, files=None, **kwargs):
        kwargs['session_config'] = self.session_config
        kwargs['for_mturk'] = self.for_mturk
        return super(CreateSession, self).get_form(data, files, **kwargs)

    def form_valid(self, form):
        pre_create_id = uuid.uuid4().hex
        kwargs = {
            'session_config_name': self.session_config['name'],
            '_pre_create_id': pre_create_id,
        }
        if self.for_mturk:
            kwargs['num_participants'] = (
                form.cleaned_data['num_participants'] *
                settings.MTURK_NUM_PARTICIPANTS_MULT
            )
        else:
            kwargs['num_participants'] = form.cleaned_data['num_participants']

        thread_create_session = threading.Thread(
            target=sleep_then_create_session,
            kwargs=kwargs,
        )
        thread_create_session.setName(pre_create_id)
        thread_create_session.start()

        self.request.session['for_mturk'] = self.for_mturk
        wait_until_session_created_url = reverse(
            'wait_until_session_created', args=(pre_create_id,)
        )
        return HttpResponseRedirect(wait_until_session_created_url)


class SessionConfigsToCreate(vanilla.View):

    @classmethod
    def url(cls):
        return "/create_session/"

    @classmethod
    def url_name(cls):
        return 'session_configs_create'

    @classmethod
    def url_pattern(cls):
        return r"^create_session/$"

    def get(self, *args, **kwargs):
        session_configs_info = []
        for session_config in get_session_configs_list():
            session_name = session_config['name']
            key = self.request.GET.get('mturk', 0)
            url = '/create_session/{}/?mturk={}'.format(session_name, key)
            session_configs_info.append(
                {'display_name': session_config['display_name'], 'url': url})
        return TemplateResponse(
            self.request, 'otree/admin/SessionListing.html',
            {'session_configs_info': session_configs_info})


class SessionMonitor(AdminSessionPageMixin, vanilla.TemplateView):

    @classmethod
    def url_name(cls):
        return 'session_monitor'

    def get_context_data(self, **kwargs):

        field_names = get_all_fields(Participant)
        rows = []
        for p in self.session.get_participants():
            row = []
            for fn in field_names:
                attr = getattr(p, fn)
                if isinstance(attr, collections.Callable):
                    attr = attr()
                row.append(attr)
            rows.append(row)

        context = super(SessionMonitor, self).get_context_data(**kwargs)
        context.update({
            'column_names': [
                pretty_name(field.strip('_')) for field in field_names
            ],
            'rows': rows,
        })
        return context


class EditSessionPropertiesForm(forms.ModelForm):

    participation_fee = forms.RealWorldCurrencyField(required=False)
    real_world_currency_per_point = forms.DecimalField(
        decimal_places=5, max_digits=12,
        required=False
    )

    class Meta:
        model = Session
        fields = [
            'label',
            'experimenter_name',
            'time_scheduled',
            'comment',
        ]

    def __init__(self, *args, **kwargs):
        super(EditSessionPropertiesForm, self).__init__(*args, **kwargs)


class EditSessionProperties(AdminSessionPageMixin, vanilla.UpdateView):

    model = Session
    form_class = EditSessionPropertiesForm
    template_name = 'otree/admin/EditSessionProperties.html'

    def get_form(self, data=None, files=None, **kwargs):
        form = super(
            EditSessionProperties, self
        ).get_form(data, files, ** kwargs)
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

    @classmethod
    def url_name(cls):
        return 'session_edit'

    def get_success_url(self):
        return reverse('session_edit', args=(self.session.pk,))

    def form_valid(self, form):
        super(EditSessionProperties, self).form_valid(form)
        config = self.session.config
        participation_fee = form.cleaned_data[
            'participation_fee'
        ]
        real_world_currency_per_point = form.cleaned_data[
            'real_world_currency_per_point'
        ]
        if form.cleaned_data['participation_fee']:
            config['participation_fee'] = RealWorldCurrency(participation_fee)
        if form.cleaned_data['real_world_currency_per_point']:
            config[
                'real_world_currency_per_point'
            ] = real_world_currency_per_point
        self.session.config = config
        self.session.save()
        messages.success(self.request, 'Properties have been updated')
        return HttpResponseRedirect(self.get_success_url())


class SessionPayments(AdminSessionPageMixin, vanilla.TemplateView):

    @classmethod
    def url_name(cls):
        return 'session_payments'

    def get_template_names(self):
        if self.session.mturk_HITId:
            return ['otree/admin/SessionMTurkPayments.html']
        else:
            return ['otree/admin/SessionPayments.html']

    def get(self, *args, **kwargs):
        response = super(SessionPayments, self).get(*args, **kwargs)
        return response

    def get_context_data(self, **kwargs):

        session = self.session
        if session.mturk_HITId:
            with MTurkConnection(
                self.request, session.mturk_sandbox
            ) as mturk_connection:
                workers_with_submit = [
                    completed_assignment.WorkerId
                    for completed_assignment in
                    mturk_connection.get_assignments(
                        session.mturk_HITId,
                        page_size=session.mturk_num_participants
                    )
                ]
                participants = session.participant_set.filter(
                    mturk_worker_id__in=workers_with_submit
                )
        else:
            participants = session.get_participants()
        total_payments = 0.0
        mean_payment = 0.0
        if participants:
            total_payments = sum(
                part.money_to_pay() or c(0) for part in participants
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


class SessionStartLinks(AdminSessionPageMixin, vanilla.TemplateView):

    @classmethod
    def url_name(cls):
        return 'session_start_links'

    def get_context_data(self, **kwargs):
        session = self.session

        participant_urls = [
            self.request.build_absolute_uri(participant._start_url())
            for participant in session.get_participants()
        ]

        anonymous_url = self.request.build_absolute_uri(
            reverse(
                'join_session_anonymously',
                args=(session._anonymous_code,)
            )
        )

        context = super(SessionStartLinks, self).get_context_data(**kwargs)

        context.update({
            'participant_urls': participant_urls,
            'anonymous_url': anonymous_url,
            'num_participants': len(participant_urls),
            'fullscreen_mode_on': len(participant_urls) <= 3
        })
        return context


class SessionResults(AdminSessionPageMixin, vanilla.TemplateView):

    @classmethod
    def url_name(cls):
        return 'session_results'

    def get_context_data(self, **kwargs):
        session = self.session

        participants = session.get_participants()
        participant_labels = [p._id_in_session() for p in participants]
        column_name_tuples = []
        rows = []

        for subsession in session.get_subsessions():
            app_label = subsession._meta.app_config.name

            column_names, subsession_rows = get_display_table_rows(
                subsession._meta.app_config.name,
                for_export=False,
                subsession_pk=subsession.pk
            )

            if not rows:
                rows = subsession_rows
            else:
                for i in range(len(rows)):
                    rows[i].extend(subsession_rows[i])

            round_number = subsession.round_number
            if round_number > 1:
                subsession_column_name = '{} [Round {}]'.format(
                    app_label, round_number
                )
            else:
                subsession_column_name = app_label

            for model_column_name, field_column_name in column_names:
                column_name_tuples.append(
                    (subsession_column_name,
                     model_column_name,
                     field_column_name)
                )

        subsession_headers = [
            (pretty_name(key), len(list(group)))
            for key, group in
            itertools.groupby(column_name_tuples, key=lambda x: x[0])
        ]

        model_headers = [
            (pretty_name(key[1]), len(list(group)))
            for key, group in
            itertools.groupby(column_name_tuples, key=lambda x: (x[0], x[1]))
        ]

        field_headers = [
            pretty_name(key[2]) for key, group in
            itertools.groupby(column_name_tuples, key=lambda x: x)
        ]

        # dictionary for json response
        # will be used only if json request  is done
        self.context_json = []
        for i, row in enumerate(rows):
            d_row = OrderedDict()
            d_row['participant_label'] = participant_labels[i]
            for t, v in zip(column_name_tuples, row):
                d_row['.'.join(t)] = v
            self.context_json.append(d_row)

        context = super(SessionResults, self).get_context_data(**kwargs)
        context.update({
            'subsession_headers': subsession_headers,
            'model_headers': model_headers,
            'field_headers': field_headers,
            'rows': rows})
        return context

    def get(self, request, *args, **kwargs):
        context = self.get_context_data()
        if self.request.META.get('CONTENT_TYPE') == 'application/json':
            return JsonResponse(self.context_json, safe=False)
        else:
            return self.render_to_response(context)


class SessionDescription(AdminSessionPageMixin, vanilla.TemplateView):

    @classmethod
    def url_name(cls):
        return 'session_description'

    def get_context_data(self, **kwargs):
        context = super(SessionDescription, self).get_context_data(**kwargs)
        context.update(session_description_dict(self.session))
        return context


def info_about_session_config(session_config):

    app_sequence = []
    seo = set()
    for app_name in session_config['app_sequence']:
        models_module = get_models_module(app_name)
        num_rounds = models_module.Constants.num_rounds
        formatted_app_name = app_name_format(app_name)
        if num_rounds > 1:
            formatted_app_name = '{} ({} rounds)'.format(
                formatted_app_name, num_rounds
            )
        subsssn = {
            'doc': getattr(models_module, 'doc', ''),
            'source_code': getattr(models_module, 'source_code', ''),
            'bibliography': getattr(models_module, 'bibliography', []),
            'links': sort_links(getattr(models_module, 'links', {})),
            'keywords': keywords_links(getattr(models_module, 'keywords', [])),
            'name': formatted_app_name,
        }
        seo.update([keywords[0] for keywords in subsssn["keywords"]])
        app_sequence.append(subsssn)
    return {
        'doc': session_config['doc'],
        'app_sequence': app_sequence,
        'page_seo': seo
    }


def sort_links(links):
    """Return the sorted .items() result from a dictionary

    """
    return sorted(links.items())


def keywords_links(keywords):
    """Create a duckduckgo.com link for every keyword

    """
    links = []
    for kw in keywords:
        kw = kw.strip()
        if kw:
            args = urlencode({"q": kw + " game theory", "t": "otree"})
            link = "https://duckduckgo.com/?{}".format(args)
            links.append((kw, link))
    return links


def session_description_dict(session):

    context_data = {
        'display_name': session.config['display_name'],
    }

    session_config = get_session_configs_dict(

    )[session.config['name']]
    context_data.update(info_about_session_config(session_config))

    return context_data


class AdminHome(vanilla.ListView):

    template_name = 'otree/admin/Home.html'

    @classmethod
    def url_pattern(cls):
        return r"^admin/(?P<archive>archive)?$"

    @classmethod
    def url_name(cls):
        return 'admin_home'

    def get_context_data(self, **kwargs):
        context = super(AdminHome, self).get_context_data(**kwargs)
        global_singleton = GlobalSingleton.objects.get()
        default_session = global_singleton.default_session
        context.update({
            'default_session': default_session,
            'is_debug': settings.DEBUG,
        })
        return context

    def get_queryset(self):
        category = otree.constants_internal.session_special_category_demo
        return Session.objects.exclude(
            special_category=category).order_by('archived', '-pk')
