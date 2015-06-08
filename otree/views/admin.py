#!/usr/bin/env python
# -*- coding: utf-8 -*-

import threading
import time
import urllib
import uuid
import itertools

from django.template.response import TemplateResponse
from django.http import HttpResponseRedirect, JsonResponse
from django.core.urlresolvers import reverse
from django.forms.forms import pretty_name
from django.conf import settings

import vanilla

from ordered_set import OrderedSet as oset
from collections import OrderedDict

import easymoney


from otree.common_internal import (
    get_models_module, app_name_format, add_params_to_url
)
from otree.session import (
    create_session, get_session_types_dict, get_session_types_list,
    get_lcm
)
from otree import forms
from otree.views.abstract import GenericWaitPageMixin, AdminSessionPageMixin

import otree.constants
import otree.models.session
from otree.common import Currency as c
from otree.models.session import Session, Participant


def get_all_fields(Model, for_export=False):

    if Model is Session:
        return [
            'code',
            'label',
            'experimenter_name',
            'real_world_currency_per_point',
            'time_scheduled'	,
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
                '_id_in_session_display',
                'code',
                'label',
                '_pages_completed',
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
                '_id_in_session_display',
                'code',
                'label',
                '_pages_completed',
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
            'session',
            '_is_missing_players',
        },
        'Subsession': {
            'code',
            'label',
            'session',
            'session_access_code',
            '_index_in_subsessions',
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
        players = Player.objects.filter(subsession_id=subsession_pk)
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
            if callable(attr):
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
            if value in values_to_replace:
                value = values_to_replace[value]
            elif for_export and isinstance(value, easymoney.Money):
                # remove currency formatting for easier analysis
                value = easymoney.to_dec(value)
            value = unicode(value).encode('UTF-8')
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
        from otree.views.concrete import AssignVisitorToOpenSession
        default_session_base_url = self.request.build_absolute_uri(
            AssignVisitorToOpenSession.url()
        )
        default_session_example_urls = []
        for i in range(1, 20):
            default_session_example_urls.append(
                add_params_to_url(
                    default_session_base_url,
                    {otree.constants.participant_label: 'P{}'.format(i)}
                )
            )
        global_singleton = otree.models.session.GlobalSingleton.objects.get()
        default_session = global_singleton.default_session

        context.update({
            'default_session_example_urls': default_session_example_urls,
            'access_code_for_default_session': (
                otree.constants.access_code_for_default_session
            ),
            'participant_label': otree.constants.participant_label,
            'default_session': default_session,
        })
        return context


class CreateSessionForm(forms.Form):

    def __init__(self, *args, **kwargs):
        self.session_type = kwargs.pop('session_type')
        super(CreateSessionForm, self).__init__(*args, **kwargs)

    num_participants = forms.IntegerField()

    def clean_num_participants(self):

        lcm = get_lcm(self.session_type)
        num_participants = self.cleaned_data['num_participants']
        if num_participants % lcm:
            raise forms.ValidationError(
                'Number of participants must be a multiple of {}'.format(lcm)
            )
        return num_participants


class WaitUntilSessionCreated(GenericWaitPageMixin, vanilla.View):

    @classmethod
    def url_pattern(cls):
        return r"^WaitUntilSessionCreated/(?P<session_pre_create_id>.+)/$"

    @classmethod
    def url(cls, pre_create_id):
        return "/WaitUntilSessionCreated/{}/".format(pre_create_id)

    def _is_ready(self):
        return Session.objects.filter(
            _pre_create_id=self._pre_create_id
        ).exists()

    def body_text(self):
        return 'Waiting until session created'

    def _response_when_ready(self):
        session = Session.objects.get(_pre_create_id=self._pre_create_id)
        session_home_url = reverse('session_start_links', args=(session.pk,))
        return HttpResponseRedirect(session_home_url)

    def dispatch(self, request, *args, **kwargs):
        self._pre_create_id = kwargs['session_pre_create_id']
        return super(WaitUntilSessionCreated, self).dispatch(
            request, *args, **kwargs
        )

    def _get_wait_page(self):
        return TemplateResponse(
            self.request, 'otree/WaitPage.html', {'view': self}
        )


def sleep_then_create_session(**kwargs):
    # hack: this sleep is to prevent locks on SQLite. This gives time to let
    # the page request finish before create_session is called,
    # because creating the session involves a lot of database I/O, which seems
    # to cause locks when multiple threads access at the same time.
    time.sleep(5)

    create_session(**kwargs)


class CreateSession(vanilla.FormView):

    form_class = CreateSessionForm
    template_name = 'otree/admin/CreateSession.html'

    @classmethod
    def url_pattern(cls):
        return r"^create_session/(?P<session_type>.+)/$"

    @classmethod
    def url_name(cls):
        return 'session_create'

    def dispatch(self, request, *args, **kwargs):
        session_type_name = urllib.unquote_plus(kwargs.pop('session_type'))
        self.session_type = get_session_types_dict()[session_type_name]
        return super(CreateSession, self).dispatch(request, *args, **kwargs)

    def get_context_data(self, **kwargs):
        context = info_about_session_type(self.session_type)
        kwargs.update(context)
        return super(CreateSession, self).get_context_data(**kwargs)

    def get_form(self, data=None, files=None, **kwargs):
        kwargs['session_type'] = self.session_type
        return super(CreateSession, self).get_form(data, files, **kwargs)

    def form_valid(self, form):
        pre_create_id = uuid.uuid4().hex
        kwargs = {
            'session_type_name': self.session_type['name'],
            'num_participants': form.cleaned_data['num_participants'],
            '_pre_create_id': pre_create_id,
        }

        threading.Thread(
            target=sleep_then_create_session,
            kwargs=kwargs,
        ).start()

        return HttpResponseRedirect(WaitUntilSessionCreated.url(pre_create_id))


class SessionTypesToCreate(vanilla.View):

    @classmethod
    def url(cls):
        return "/create_session/"

    @classmethod
    def url_name(cls):
        return 'session_types_create'

    @classmethod
    def url_pattern(cls):
        return r"^create_session/$"

    def get(self, *args, **kwargs):
        session_types_info = []
        for session_type in get_session_types_list():
            session_types_info.append(
                {
                    'display_name': session_type['display_name'],
                    'url': '/create_session/{}/'.format(session_type['name']),
                }
            )

        return TemplateResponse(self.request,
                                'otree/admin/SessionListing.html',
                                {'session_types_info': session_types_info})


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
                if callable(attr):
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


class EditSessionProperties(AdminSessionPageMixin, vanilla.UpdateView):

    model = Session
    fields = [
        'label',
        'experimenter_name',
        'real_world_currency_per_point',
        'time_scheduled',
        'archived',
        'participation_fee',
        'comment',
    ]

    def get_form(self, data=None, files=None, **kwargs):
        form = super(
            EditSessionProperties, self
        ).get_form(data, files, ** kwargs)
        if self.session.mturk_HITId:
            form.fields['participation_fee'].widget.attrs['readonly'] = 'True'
        return form

    @classmethod
    def url_name(cls):
        return 'session_edit'

    def get_success_url(self):
        return reverse('session_edit', args=(self.session.pk,))


class SessionPayments(AdminSessionPageMixin, vanilla.TemplateView):

    @classmethod
    def url_name(cls):
        return 'session_payments'

    def get_template_names(self):
        if self.session.mturk_HITId:
            return 'otree/admin/SessionMTurkPayments.html'
        else:
            return 'otree/admin/SessionPayments.html'

    def get(self, *args, **kwargs):
        response = super(SessionPayments, self).get(*args, **kwargs)
        return response

    def get_context_data(self, **kwargs):

        session = self.session
        if session.mturk_HITId:
            participants = session.participant_set.exclude(
                mturk_assignment_id__isnull=True
            ).exclude(mturk_assignment_id="")
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
            'participation_fee': session.participation_fee,
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
        participant_labels = [p._id_in_session_display() for p in participants]
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


def info_about_session_type(session_type):

    app_sequence = []
    seo = set()
    for app_name in session_type['app_sequence']:
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
        seo.update(map(lambda (a, b): a, subsssn["keywords"]))
        app_sequence.append(subsssn)
    return {
        'doc': session_type['doc'],
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
            args = urllib.urlencode({"q": kw + " game theory", "t": "otree"})
            link = "https://duckduckgo.com/?{}".format(args)
            links.append((kw, link))
    return links


def session_description_dict(session):

    context_data = {
        'display_name': session.session_type['display_name'],
    }

    session_type = get_session_types_dict(

    )[session.session_type['name']]
    context_data.update(info_about_session_type(session_type))

    return context_data


class AdminHome(vanilla.ListView):

    template_name = 'otree/admin/Home.html'

    @classmethod
    def url_pattern(cls):
        return r"^admin/(?P<archive>archive)?$"

    @classmethod
    def url_name(cls):
        return 'admin_home'

    def dispatch(self, request, *args, **kwargs):
        if kwargs['archive'] == 'archive':
            self.is_archive_request = True
        else:
            self.is_archive_request = False
        return super(AdminHome, self).dispatch(
            request, *args, **kwargs
        )

    def get_context_data(self, **kwargs):
        context = super(AdminHome, self).get_context_data(**kwargs)
        global_singleton = otree.models.session.GlobalSingleton.objects.get()
        default_session = global_singleton.default_session
        context.update({
            'archive_list_view': self.is_archive_request,
            'has_archived_sessions': (
                Session.objects.filter(
                    archived=True
                ).count() > 0
            ),
            'default_session': default_session,
            'is_debug': settings.DEBUG,
            'is_mturk_set': (
                settings.AWS_SECRET_ACCESS_KEY and settings.AWS_ACCESS_KEY_ID
            )
        })
        return context

    def get_queryset(self):
        return Session.objects.filter(
            archived=self.is_archive_request
        ).exclude(
            special_category=otree.constants.session_special_category_demo
        )
