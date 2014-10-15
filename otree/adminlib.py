from collections import OrderedDict
import time

from django.contrib import admin
from django.conf.urls import patterns
from django.template.response import TemplateResponse
from django.core.urlresolvers import reverse
import django.db.models.options
import django.db.models.fields.related
from django.http import HttpResponse, HttpResponseBadRequest
from django.contrib.staticfiles.templatetags.staticfiles import static as static_template_tag
from otree.session import SessionTypeDirectory
from otree.views.demo import render_to_start_links_page

import otree.constants
import otree.sessionlib.models
from otree.sessionlib.models import Participant, Session
from otree.common import currency, add_params_to_url

def new_tab_link(url, label):
    return '<a href="{}" target="_blank">{}</a>'.format(url, label)

def remove_duplicates(lst):
    return list(OrderedDict.fromkeys(lst))

def get_callables(Model, fields_specific_to_this_subclass=None, for_export=False):

    fields_specific_to_this_subclass = fields_specific_to_this_subclass or []

    export_and_changelist = {
        'Player': [],
        'Group': [],
        'Subsession': [],
        'Session': [],
        'Participant': [],
    }[Model.__name__]

    changelist_but_not_export = {
        'Player':
           ['name',
            'link',
            '_pages_completed'],
        'Group':
            [],
        'Subsession':
            [],
        'Session': [
             'start_links_link',
             'participants_table_link',
             'raw_participant_urls_link',
             'payments_ready',
             'payments_link',
             'base_pay_display',
             'is_open',
        ],
        'Participant': [
                'subsessions_completed',
                'current_subsession',
                '_pages_completed_in_current_subsession',
                'status',
                'start_link',
            ],
    }[Model.__name__]

    export_but_not_changelist = {
        'Player': [],
        'Group': [],
        'Subsession': [],
        'Session': [],
        'Participant': [],
    }[Model.__name__]

    if for_export:
        callables = export_and_changelist + export_but_not_changelist
    else:
        callables = export_and_changelist + changelist_but_not_export

    return remove_duplicates(callables + fields_specific_to_this_subclass)

def get_readonly_fields(Model, fields_specific_to_this_subclass=None):
    callables = get_callables(Model, fields_specific_to_this_subclass)

    for_change_page_and_list = {
        'Player': [],
        'Group': [],
        'Subsession': [],
        'Session': [
            'code',
            'type_name',
            'time_started',
            '_players_assigned_to_groups',
            'special_category',
        ],
        'Participant': [],
    }[Model.__name__]

    return remove_duplicates(callables + for_change_page_and_list)

def get_all_fields_for_table(Model, callables, first_fields=None, for_export=False):

    first_fields = {
        'Player':
            [
                'id',
                'name',
                'session',
                'subsession',
                'group',
                'id_in_group',
                'role',
                'visited',
                '_pages_completed'
            ],
        'Group':
            [
                'id',
                'session',
                'subsession',
            ],
        'Subsession':
            ['name',
             'session'],
        'Participant':
            [
                'code',
                'label',
                'name',
                'start_link',
                'session',
                'visited',
                'subsessions_completed',
                'current_subsession',
                '_pages_completed_in_current_subsession',
                'current_page',
                'status',
                'last_request_succeeded',
            ],
        'Session':
            [
                'code',
                'type_name',
                'label',
                'hidden',
                'type',
            ],
    }[Model.__name__]

    last_fields = {
        'Player': [],
        'Group': [],
        'Subsession': [],
        'Participant': [
            'start_link',
            'exclude_from_data_analysis',
        ],
        'Session': [
        ],
    }[Model.__name__]

    fields_for_export_but_not_changelist = {
        'Player': {'id', 'label'},
        'Group': {'id'},
        'Subsession': {'id'},
        'Session': {
            'git_commit_timestamp',
            'base_pay',
        },
        'Participant': {
            #'label',
            'ip_address',
        },
    }[Model.__name__]

    fields_for_changelist_but_not_export = {
        'Player': {'group', 'subsession', 'session', 'participant'},
        'Group': {'subsession', 'session'},
        'Subsession': {'session'},
        'Session': {
            'players_assigned_to_groups',
            'hidden',
        },
        'Participant': {
            'session',
            'name',
            'start_link',
            'session',
            'visited',
            # the following fields are useful for telling if the participant actually finished
            #'subsessions_completed',
            #'current_subsession',
            #'_pages_completed_in_current_subsession',
            #'current_page',
            'status',
            'last_request_succeeded',
        },
    }[Model.__name__]

    fields_to_exclude_from_export_and_changelist = {
        'Player':
              {
              # we should only have participant code and session code. because those are real world concepts.
              # person/session.
              # also, people might confuse player/subsession code with participant/session code
              'code',
              'index_in_pages',
              '_me_in_previous_subsession_content_type',
              '_me_in_previous_subsession_object_id',
              '_me_in_next_subsession_content_type',
              '_me_in_next_subsession_object_id',
              'participant',
              },
        'Group':
             set(),
        'Subsession':
            {
                'code',
                'label',
                'session_access_code',
                '_next_subsession_content_type',
                '_next_subsession_object_id',
                'next_subsession',
                '_previous_subsession_content_type',
                '_previous_subsession_object_id',
                'previous_subsession',
                '_experimenter',
             },
        'Participant':
            {
                'id',
                '_index_in_subsessions',
                'me_in_first_subsession_content_type',
                'me_in_first_subsession_object_id',
                'is_on_wait_page',
                'mturk_assignment_id',
                'mturk_worker_id',
                'vars',
            },
        'Session':
             {
             'mturk_payment_was_sent',
             'id', # can't be shown on change page, because pk not editable?
             'session_experimenter',
             'subsession_names',
             'first_subsession_content_type',
             'first_subsession_object_id',
             'first_subsession',
             'is_for_mturk',
             'demo_already_used',
             'ready',
             'vars',
             # don't hide the code, since it's useful as a checksum (e.g. if you're on the payments page)
             }
    }[Model.__name__]

    if for_export:
        fields_to_exclude = fields_to_exclude_from_export_and_changelist.union(fields_for_changelist_but_not_export)
    else:
        fields_to_exclude = fields_to_exclude_from_export_and_changelist.union(fields_for_export_but_not_changelist)

    all_field_names = [field.name for field in Model._meta.fields if field.name not in fields_to_exclude]
    all_member_names = set(callables + all_field_names)
    first_fields = [f for f in first_fields if f in all_member_names]
    last_fields = [f for f in last_fields if f in all_member_names]
    table_columns = first_fields + callables + all_field_names
    table_columns = [f for f in table_columns if f not in last_fields] + last_fields

    if for_export:
        return remove_duplicates(table_columns)
    else:
        return _add_links_for_foreign_keys(Model, remove_duplicates(table_columns))


def get_all_fields_for_change_page(Model, readonly_fields):

    table_fields = get_all_fields_for_table(Model, readonly_fields)

    for_change_page_only = {
        'Player': [],
        'Group': [],
        'Subsession': [],
        'Session': [
            'time_scheduled',
            'comment',
        ],
        'Participant': [],
    }[Model.__name__]

    return remove_duplicates(table_fields + for_change_page_only)



def get_list_display(Model, readonly_fields, first_fields=None):
    return get_all_fields_for_table(Model, callables=readonly_fields, first_fields=first_fields, for_export=False)

class FieldLinkToForeignKey:
    def __init__(self, list_display_field):
        self.list_display_field = list_display_field

    @property
    def __name__(self):
        return self.list_display_field

    def __repr__(self):
        return self.list_display_field

    def __str__(self):
        return self.list_display_field

    def __call__(self, instance):
        object = getattr(instance, self.list_display_field)
        if object is None:
            return "(None)"
        else:
            url = reverse('admin:%s_%s_change' %(object._meta.app_label,  object._meta.module_name),
                            args=[object.id])
            return '<a href="%s">%s</a>' % (url, object.__unicode__())

    @property
    def allow_tags(self):
        return True

def _add_links_for_foreign_keys(model, list_display_fields):

    result = []
    for list_display_field in list_display_fields:
        if hasattr(model, list_display_field):
            try:
                if isinstance(model._meta.get_field(list_display_field),
                              django.db.models.fields.related.ForeignKey):
                    result.append(FieldLinkToForeignKey(list_display_field))
                    continue
            except django.db.models.options.FieldDoesNotExist:
                pass
        result.append(list_display_field)
    return result

class NonHiddenSessionListFilter(admin.SimpleListFilter):
    title = "session"

    parameter_name = "session"

    def lookups(self, request, model_admin):
        """
        Returns a list of tuples. The first element in each
        tuple is the coded value for the option that will
        appear in the URL query. The second element is the
        human-readable name for the option that will appear
        in the right sidebar.
        """
        return [(session.id, session.id) for session
                in otree.sessionlib.models.Session.objects.filter(hidden=False)]

    def queryset(self, request, queryset):
        """
        Returns the filtered queryset based on the value
        provided in the query string and retrievable via
        `self.value()`.
        """
        if self.value() is not None:
            return queryset.filter(session__pk=self.value())
        else:
            return queryset

class OTreeBaseModelAdmin(admin.ModelAdmin):
    """Allow leaving fields blank in the admin"""
    def get_form(self, request, obj=None, **kwargs):
        form = super(OTreeBaseModelAdmin, self).get_form(request, obj, **kwargs)
        for key in form.base_fields.keys():
            try:
                model_field, _, _, _ = self.model._meta.get_field_by_name(key)
                if model_field.null:
                    form.base_fields[key].required = False
            except django.db.models.options.FieldDoesNotExist:
                pass
        return form

CHANGE_LIST_TEMPLATE = "admin/otree_change_list.html"

class PlayerAdmin(OTreeBaseModelAdmin):
    change_list_template = CHANGE_LIST_TEMPLATE

    def link(self, instance):
        url = instance._start_url()
        return new_tab_link(url, 'Link')

    link.short_description = "Start link"
    link.allow_tags = True
    list_filter = [NonHiddenSessionListFilter, 'subsession', 'group']
    list_per_page = 40

    def queryset(self, request):
        qs = super(PlayerAdmin, self).queryset(request)
        return qs.filter(session__hidden=False)

class GroupAdmin(OTreeBaseModelAdmin):
    change_list_template = CHANGE_LIST_TEMPLATE

    list_filter = [NonHiddenSessionListFilter, 'subsession']
    list_per_page = 40

    def queryset(self, request):
        qs = super(GroupAdmin, self).queryset(request)
        return qs.filter(session__hidden=False)

class SubsessionAdmin(OTreeBaseModelAdmin):
    change_list_template = CHANGE_LIST_TEMPLATE

    def queryset(self, request):
        qs = super(SubsessionAdmin, self).queryset(request)
        return qs.filter(session__hidden=False)

    list_filter = [NonHiddenSessionListFilter]
    list_editable = ['_skip']

class GlobalSettingsAdmin(OTreeBaseModelAdmin):
    list_display = ['id', 'open_session', 'persistent_urls_link', 'mturk_snippet_link']
    list_editable = ['open_session']

    def get_urls(self):
        urls = super(GlobalSettingsAdmin, self).get_urls()
        my_urls = patterns('',
            (r'^(?P<pk>\d+)/mturk_snippet/$', self.admin_site.admin_view(self.mturk_snippet)),
            (r'^(?P<pk>\d+)/persistent_urls/$', self.admin_site.admin_view(self.persistent_urls)),
        )
        return my_urls + urls

    def persistent_urls_link(self, instance):
        return new_tab_link('{}/persistent_urls/'.format(instance.pk), 'Link')
    persistent_urls_link.allow_tags = True
    persistent_urls_link.short_description = "Persistent URLs"

    def persistent_urls(self, request, pk):
        from otree.views.concrete import AssignVisitorToOpenSession
        open_session_base_url = request.build_absolute_uri(AssignVisitorToOpenSession.url())
        open_session_example_url = add_params_to_url(open_session_base_url, {otree.constants.participant_label: 'P1'})

        return TemplateResponse(
            request,
            'otree/admin/PersistentLabURLs.html',
            {
                'open_session_example_url': open_session_example_url,
                'access_code_for_open_session': otree.constants.access_code_for_open_session,
                'participant_label': otree.constants.participant_label
            }
        )

    def mturk_snippet_link(self, instance):
        return new_tab_link('{}/mturk_snippet/'.format(instance.pk), 'Link')

    def mturk_snippet(self, request, pk):
        hit_page_js_url = request.build_absolute_uri(static_template_tag('otree/js/mturk_hit_page.js'))
        from otree.views.concrete import AssignVisitorToOpenSessionMTurk
        open_session_url = request.build_absolute_uri(AssignVisitorToOpenSessionMTurk.url())

        return TemplateResponse(request,
                                'otree/admin/MTurkSnippet.html',
                                {'hit_page_js_url': hit_page_js_url,
                                 'open_session_url': open_session_url,},
                                content_type='text/plain')


    mturk_snippet_link.allow_tags = True
    mturk_snippet_link.short_description = "HTML snippet for MTurk HIT page"

    def mturk_snippet(self, request, pk):
        hit_page_js_url = request.build_absolute_uri(static_template_tag('otree/js/mturk_hit_page.js'))
        from otree.views.concrete import AssignVisitorToOpenSessionMTurk
        open_session_url = request.build_absolute_uri(AssignVisitorToOpenSessionMTurk.url())

        return TemplateResponse(context, 'otree/admin/MTurkSnippet.html',
                                {'hit_page_js_url': hit_page_js_url,
                                 'open_session_url': open_session_url,},
                                content_type='text/plain')




class ParticipantAdmin(OTreeBaseModelAdmin):
    change_list_template = CHANGE_LIST_TEMPLATE

    list_filter = [NonHiddenSessionListFilter]

    readonly_fields = get_callables(otree.sessionlib.models.Participant, [])
    list_display = get_all_fields_for_table(otree.sessionlib.models.Participant, readonly_fields)
    list_editable = ['exclude_from_data_analysis']


    def start_link(self, instance):
        url = instance._start_url()
        return new_tab_link(url, 'Link')
    start_link.allow_tags = True

    def queryset(self, request):
        qs = super(ParticipantAdmin, self).queryset(request)
        return qs.filter(session__hidden=False)

class SessionAdmin(OTreeBaseModelAdmin):
    change_list_template = CHANGE_LIST_TEMPLATE

    def get_urls(self):
        urls = super(SessionAdmin, self).get_urls()
        my_urls = patterns('',
            (r'^(?P<pk>\d+)/payments/$', self.admin_site.admin_view(self.payments)),
            (r'^(?P<pk>\d+)/raw_participant_urls/$', self.raw_participant_urls),
            (r'^(?P<pk>\d+)/start_links/$', self.start_links),
        )
        return my_urls + urls

    def participants_table_link(self, instance):

        participants_table_url = reverse('admin:%s_%s_changelist' % (Participant._meta.app_label, Participant._meta.module_name))
        return new_tab_link(
            add_params_to_url(participants_table_url, {'session': instance.pk}),
            'Link'
        )
    participants_table_link.allow_tags = True
    participants_table_link.short_description = 'Monitor participants'

    def participant_urls(self, request, session):
        participants = session.get_participants()
        return [request.build_absolute_uri(participant._start_url()) for participant in participants]

    def start_links(self, request, pk):
        session = self.model.objects.get(pk=pk)
        return render_to_start_links_page(request, session, is_demo_page=False)

    def start_links_link(self, instance):
        return new_tab_link(
            '/admin/sessionlib/session/{}/start_links/'.format(instance.pk),
            'Link'
        )

    start_links_link.short_description = 'Start links'
    start_links_link.allow_tags = True


    def raw_participant_urls(self, request, pk):
        session = self.model.objects.get(pk=pk)

        if request.GET.get(otree.constants.session_user_code) != session.session_experimenter.code:
            return HttpResponseBadRequest('{} parameter missing or incorrect'.format(otree.constants.session_user_code))
        urls = self.participant_urls(request, session)
        return HttpResponse('\n'.join(urls), content_type="text/plain")


    def raw_participant_urls_link(self, instance):
        return new_tab_link('/admin/sessionlib/session/{}/raw_participant_urls/?{}={}'.format(instance.pk,
                                                          otree.constants.session_user_code,
                                                          instance.session_experimenter.code), 'Link')

    raw_participant_urls_link.short_description = 'Participant URLs'
    raw_participant_urls_link.allow_tags = True



    def payments(self, request, pk):
        session = self.model.objects.get(pk=pk)
        participants = session.get_participants()
        total_payments = sum(participant.total_pay() or 0 for participant in participants)

        try:
            mean_payment = total_payments/len(participants)
        except ZeroDivisionError:
            mean_payment = 0


        return TemplateResponse(request, 'otree/admin/Payments.html',
                                {'participants': participants,
                                'total_payments': total_payments,
                                'mean_payment': mean_payment,
                                'session_code': session.code,
                                'session_name': session,
                                'base_pay': session.base_pay,
                                })

    def payments_link(self, instance):
        if instance.payments_ready():
            link_text = 'Ready'
        else:
            link_text = 'Incomplete'
        #FIXME: use proper URL
        return new_tab_link('/admin/sessionlib/session/{}/payments/'.format(instance.pk), link_text)

    payments_link.short_description = "Payments page"
    payments_link.allow_tags = True

    readonly_fields = get_readonly_fields(otree.sessionlib.models.Session, [])
    list_display = get_all_fields_for_table(otree.sessionlib.models.Session, readonly_fields)

    fields = get_all_fields_for_change_page(otree.sessionlib.models.Session, readonly_fields)

    list_editable = ['hidden']



def autodiscover():
    """
    This function is copied from django 1.6's django/contrib/admin/__init__.py
    I'm modifying it to look instead for _builtin.admin.
    In Django 1.7, I will want to use django.utils.module_loading.autodiscover_modules,
    which is better abstracted.
    """

    from django.contrib.admin.sites import site
    import copy
    from django.conf import settings
    from django.utils.importlib import import_module
    from django.utils.module_loading import module_has_submodule

    for app in settings.INSTALLED_APPS:
        if app in settings.INSTALLED_OTREE_APPS:
            admin_module_dotted_path = '_builtin.admin'
        else:
            admin_module_dotted_path = 'admin'

        mod = import_module(app)
        # Attempt to import the app's admin module.
        try:
            before_import_registry = copy.copy(site._registry)
            import_module('{}.{}'.format(app, admin_module_dotted_path))
        except:
            # Reset the model registry to the state before the last import as
            # this import will have to reoccur on the next request and this
            # could raise NotRegistered and AlreadyRegistered exceptions
            # (see #8245).
            site._registry = before_import_registry

            # Decide whether to bubble up this error. If the app just
            # doesn't have an admin module, we can ignore the error
            # attempting to import it, otherwise we want it to bubble up.
            if module_has_submodule(mod, admin_module_dotted_path):
                raise
