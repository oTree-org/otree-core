from collections import OrderedDict
import time

from django.contrib import admin
from django.conf.urls import patterns
from django.shortcuts import render_to_response
from django.core.urlresolvers import reverse
import django.db.models.options
import django.db.models.fields.related
from django.http import HttpResponse, HttpResponseBadRequest
from django.contrib.staticfiles.templatetags.staticfiles import static as static_template_tag

import ptree.constants
import ptree.sessionlib.models
from ptree.common import currency

def new_tab_link(url, label):
    return '<a href="{}" target="_blank">{}</a>'.format(url, label)

def remove_duplicates(lst):
    return list(OrderedDict.fromkeys(lst))

def get_readonly_fields(Model, fields_specific_to_this_subclass=None):

    fields_for_this_model_type = {
        'Participant':
           ['name',
            'link',
            'pages_completed'],
        'Match':
            [],
        'Treatment':
            [],
        'Subsession':
            [],
        'Session': [
             'subsession_names',
             'start_links_link',
             'raw_participant_urls_link',
             'magdeburg_start_urls_link',
             'payments_ready',
             'payments_link',
             'base_pay_display',
        ],
        'SessionParticipant': [
                'start_link',
                'subsessions_completed',
                'current_subsession',
                'pages_completed_in_current_subsession',
                'status'
            ],
    }[Model.__name__]

    return remove_duplicates(fields_for_this_model_type + (fields_specific_to_this_subclass or []))

def get_list_display(Model, readonly_fields, first_fields=None):

    first_fields = {
        'Participant':
            ['name',
            'session',
            'subsession',
            'treatment',
            'match',
            'visited',
            'pages_completed'],
        'Match':
            ['id',
            'session',
            'subsession',
            'treatment'],
        'Treatment':
            ['name',
            'session',
            'subsession'],
        'Subsession':
            ['name',
             'session'],
        'SessionParticipant':
            ['name',
             'start_link',
             'session',
             'visited',
             'subsessions_completed',
             'current_subsession',
             'pages_completed_in_current_subsession',
             'current_page',
             'status',
             'last_request_succeeded',
            ],
        'Session':
            ['name',
             'hidden'],
    }[Model.__name__]

    last_fields = {
        'Participant': [],
        'Match': [],
        'Treatment': [],
        'Subsession': [],
        'SessionParticipant': [
            'start_link',
            'exclude_from_data_analysis',
        ],
        'Session': [

            'comment',
        ],
    }[Model.__name__]


    fields_to_exclude = {
        'Participant':
              {'id',
              'code',
              'index_in_pages',
              'me_in_previous_subsession_content_type',
              'me_in_previous_subsession_object_id',
              'me_in_next_subsession_content_type',
              'me_in_next_subsession_object_id',
              'session_participant',
              },
        'Match':
             set(),
        'Treatment':
            {'id',
            'label'},
        'Subsession':
            {
                'id',
                'label',
                'session_access_code',
                'next_subsession_content_type',
                'next_subsession_object_id',
                'next_subsession',
                'previous_subsession_content_type',
                'previous_subsession_object_id',
                'previous_subsession',
                'experimenter',
             },
        'SessionParticipant':
            {'id',
            'index_in_subsessions',
            'label',
            'me_in_first_subsession_content_type',
            'me_in_first_subsession_object_id',
            'is_on_wait_page',
            'ip_address',
            'mturk_assignment_id',
            'mturk_worker_id'},
        'Session':
             {'id',
             'label',
             'session_experimenter',
             'first_subsession_content_type',
             'first_subsession_object_id',
             'first_subsession',
             'git_hash',
             'is_for_mturk',
             'base_pay',
             # don't hide the code, since it's useful as a checksum (e.g. if you're on the payments page)
             }
    }[Model.__name__]





    all_field_names = [field.name for field in Model._meta.fields if field.name not in fields_to_exclude]
    list_display = first_fields + readonly_fields + all_field_names
    list_display = [f for f in list_display if f not in last_fields] + last_fields
    return _add_links_for_foreign_keys(Model, remove_duplicates(list_display))

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
                in ptree.sessionlib.models.Session.objects.filter(hidden=False)]

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

class PTreeBaseModelAdmin(admin.ModelAdmin):
    """Allow leaving fields blank in the admin"""
    def get_form(self, request, obj=None, **kwargs):
        form = super(PTreeBaseModelAdmin, self).get_form(request, obj, **kwargs)
        for key in form.base_fields.keys():
            try:
                model_field, _, _, _ = self.model._meta.get_field_by_name(key)
                if model_field.null:
                    form.base_fields[key].required = False
            except django.db.models.options.FieldDoesNotExist:
                pass
        return form

class ParticipantAdmin(PTreeBaseModelAdmin):
    change_list_template = "admin/ptree_change_list.html"

    def link(self, instance):
        url = instance.start_url()
        return new_tab_link(url, 'Link')

    link.short_description = "Start link"
    link.allow_tags = True
    list_filter = [NonHiddenSessionListFilter, 'subsession', 'treatment', 'match']
    list_per_page = 40

    def queryset(self, request):
        qs = super(ParticipantAdmin, self).queryset(request)
        return qs.filter(session__hidden=False)

class MatchAdmin(PTreeBaseModelAdmin):
    change_list_template = "admin/ptree_change_list.html"

    list_filter = [NonHiddenSessionListFilter, 'subsession', 'treatment']
    list_per_page = 40

    def queryset(self, request):
        qs = super(MatchAdmin, self).queryset(request)
        return qs.filter(session__hidden=False)

class TreatmentAdmin(PTreeBaseModelAdmin):
    change_list_template = "admin/ptree_change_list.html"

    list_filter = [NonHiddenSessionListFilter, 'subsession']

    def queryset(self, request):
        qs = super(TreatmentAdmin, self).queryset(request)
        return qs.filter(session__hidden=False)


class SubsessionAdmin(PTreeBaseModelAdmin):
    change_list_template = "admin/ptree_change_list.html"

    def queryset(self, request):
        qs = super(SubsessionAdmin, self).queryset(request)
        return qs.filter(session__hidden=False)

    list_filter = [NonHiddenSessionListFilter]
    list_editable = ['skip']

class SessionParticipantAdmin(PTreeBaseModelAdmin):
    change_list_template = "admin/ptree_change_list.html"

    list_filter = [NonHiddenSessionListFilter]

    readonly_fields = get_readonly_fields(ptree.sessionlib.models.SessionParticipant, [])
    list_display = get_list_display(ptree.sessionlib.models.SessionParticipant, readonly_fields)
    list_editable = ['exclude_from_data_analysis']


    def start_link(self, instance):
        url = instance.start_url()
        return new_tab_link(url, 'Link')
    start_link.allow_tags = True

    def queryset(self, request):
        qs = super(SessionParticipantAdmin, self).queryset(request)
        return qs.filter(session__hidden=False)

class SessionAdmin(PTreeBaseModelAdmin):
    change_list_template = "admin/ptree_change_list.html"

    def get_urls(self):
        urls = super(SessionAdmin, self).get_urls()
        my_urls = patterns('',
            (r'^(?P<pk>\d+)/payments/$', self.admin_site.admin_view(self.payments)),
            (r'^(?P<pk>\d+)/raw_participant_urls/$', self.raw_participant_urls),
            (r'^(?P<pk>\d+)/start_links/$', self.start_links),
            (r'^(?P<pk>\d+)/magdeburg_start_urls/$', self.magdeburg_start_urls),
        )
        return my_urls + urls

    def participant_urls(self, request, session):
        participants = session.participants()
        return [request.build_absolute_uri(participant.start_url()) for participant in participants]

    def start_links(self, request, pk):
        session = self.model.objects.get(pk=pk)

        return render_to_response(
            'admin/StartLinks.html',
            {
                'experimenter_url': request.build_absolute_uri(session.session_experimenter.start_url()),
                'participant_urls': self.participant_urls(request, session),
            }
        )

    def start_links_link(self, instance):
        return new_tab_link(
            '{}/start_links/'.format(instance.pk),
            'Link'
        )

    start_links_link.short_description = 'Start links'
    start_links_link.allow_tags = True


    def raw_participant_urls(self, request, pk):
        session = self.model.objects.get(pk=pk)

        if request.GET.get(ptree.constants.session_user_code) != session.session_experimenter.code:
            return HttpResponseBadRequest('{} parameter missing or incorrect'.format(ptree.constants.session_user_code))
        urls = self.participant_urls(request, session)
        return HttpResponse('\n'.join(urls), content_type="text/plain")


    def raw_participant_urls_link(self, instance):
        return new_tab_link('{}/raw_participant_urls/?{}={}'.format(instance.pk,
                                                          ptree.constants.session_user_code,
                                                          instance.session_experimenter.code), 'Link')

    raw_participant_urls_link.short_description = 'Participant URLs'
    raw_participant_urls_link.allow_tags = True

    def magdeburg_start_urls(self, request, pk):
        session = self.model.objects.get(pk=pk)
        codes = [session_participant.code for session_participant in session.participants()]

        import_file_lines = []
        for i, code in enumerate(codes):
            import_file_lines.append(
                'maxlab-{} | 1 | /name {}&{}={}&{}={}'.format(
                    str(i+1).zfill(2),
                    i+1,
                    ptree.constants.session_user_code,
                    code,
                    ptree.constants.session_participant_label,
                    i+1
                )
            )
        response = HttpResponse('\n'.join(import_file_lines), content_type="text/plain")
        response['Content-Disposition'] = 'attachment; filename="{}"'.format('ptree-{}.ini'.format(time.time()))
        return response

    def magdeburg_start_urls_link(self, instance):
        return new_tab_link('{}/magdeburg_start_urls/?{}={}'.format(instance.pk,
                                                          ptree.constants.session_user_code,
                                                          instance.session_experimenter.code), 'Link')

    magdeburg_start_urls_link.short_description = 'Magdeburg Start URLs'
    magdeburg_start_urls_link.allow_tags = True

    def payments(self, request, pk):
        session = self.model.objects.get(pk=pk)
        participants = session.participants()
        total_payments = sum(participant.total_pay() or 0 for participant in session.participants())

        try:
            mean_payment = total_payments/len(participants)
        except ZeroDivisionError:
            mean_payment = 0


        return render_to_response('admin/Payments.html',
                                  {'participants': participants,
                                  'total_payments': currency(total_payments),
                                  'mean_payment': currency(mean_payment),
                                  'session_code': session.code,
                                  'session_name': session,
                                  'base_pay': currency(session.base_pay),
                                  })

    def payments_link(self, instance):
        if instance.payments_ready():
            link_text = 'Ready'
        else:
            link_text = 'Incomplete'
        return new_tab_link('{}/payments/'.format(instance.pk), link_text)

    payments_link.short_description = "Payments page"
    payments_link.allow_tags = True

    readonly_fields = get_readonly_fields(ptree.sessionlib.models.Session, [])
    list_display = get_list_display(ptree.sessionlib.models.Session, readonly_fields)

    list_editable = ['hidden']

def autodiscover():
    """
    This function is copied from django 1.6's django/contrib/admin/__init__.py
    I'm modifying it to look instead for utilities.admin.
    In Django 1.7, I will want to use django.utils.module_loading.autodiscover_modules,
    which is better abstracted.
    """

    from django.contrib.admin.sites import site
    import copy
    from django.conf import settings
    from django.utils.importlib import import_module
    from django.utils.module_loading import module_has_submodule

    for app in settings.INSTALLED_APPS:
        if app in settings.INSTALLED_PTREE_APPS:
            admin_module_dotted_path = 'utilities.admin'
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
