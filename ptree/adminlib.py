from collections import OrderedDict
from django.contrib import admin
from django.conf.urls import patterns
from django.shortcuts import render_to_response
from django.core.urlresolvers import reverse
import django.db.models.options
import django.db.models.fields.related
import ptree.constants
from django.http import HttpResponse, HttpResponseBadRequest
from django.contrib.staticfiles.templatetags.staticfiles import static as static_template_tag
import ptree.session.models
from ptree.common import currency

def new_tab_link(url, label):
    return '<a href="{}" target="_blank">{}</a>'.format(url, label)

def start_urls_for_experiment(experiment, request):
    if request.GET.get(ptree.constants.experimenter_access_code) != experiment.experimenter_access_code:
        return HttpResponseBadRequest('{} parameter missing or incorrect'.format(ptree.constants.experimenter_access_code))
    participants = experiment.participants()
    urls = [request.build_absolute_uri(participant.start_url()) for participant in participants]
    return HttpResponse('\n'.join(urls), content_type="text/plain")

def remove_duplicates(lst):
    return list(OrderedDict.fromkeys(lst))

def get_readonly_fields(Model, fields_specific_to_this_subclass=None):

    fields_for_this_model_type = {
        'Participant':
           ['name',
            'link',
            'bonus_display',
            'progress'],
        'Match':
            [],
        'Treatment':
            ['link'],
        'Experiment':
            ['experimenter_input_link'],
        'Session':
            ['time_started',
             'experiment_names',
             'start_urls_link',
             'global_start_link',
             'mturk_snippet_link',
             'payments_link'],
        'SessionParticipant':
            ['bonus_display',
            'start_link',
            'progress'],
    }[Model.__name__]

    return remove_duplicates(fields_for_this_model_type + (fields_specific_to_this_subclass or []))

def get_list_display(Model, readonly_fields, first_fields=None):

    first_fields = {
        'Participant':
            ['name',
            'session',
            'experiment',
            'treatment',
            'match',
            'visited',
            'progress'],
        'Match':
            ['id',
            'session',
            'experiment',
            'treatment'],
        'Treatment':
            ['name',
            'session',
            'experiment'],
        'Experiment':
            ['name',
             'session'],
        'SessionParticipant':
            ['name',
             'progress'],
        'Session':
            ['name',
             'hidden'],
    }[Model.__name__]

    fields_to_exclude = {
        'Participant':
              ['id',
              'code',
              'index_in_sequence_of_views',
              'me_in_previous_experiment_content_type',
              'me_in_previous_experiment_object_id',
              'me_in_next_experiment_content_type',
              'me_in_next_experiment_object_id',
              'session_participant',
              ],
        'Match':
             [],
        'Treatment':
            ['id',
            'label'],
        'Experiment':
            ['id',
             'label',
             'session_access_code',
             'next_experiment_content_type',
             'next_experiment_object_id',
             'next_experiment',
             'previous_experiment_content_type',
             'previous_experiment_object_id',
             'previous_experiment',
             'experimenter_access_code',
             ],
        'SessionParticipant':
            ['id',
            'index_in_session',
            'label',
            'me_in_first_experiment_content_type',
            'me_in_first_experiment_object_id'],
        'Session':
             ['id',
             'label',
             'first_experiment_content_type',
             'first_experiment_object_id',
             'first_experiment']
    }[Model.__name__]

    all_field_names = [field.name for field in Model._meta.fields if field.name not in fields_to_exclude]
    list_display = first_fields + readonly_fields + all_field_names
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
            return '<a href="%s">%s</a>' % (url, object.pk)

    @property
    def allow_tags(self):
        return True

def is_fk_link_to_parent_class(field):
    return isinstance(field, FieldLinkToForeignKey) and field.__name__ in {'match', 'treatment', 'experiment', 'session'}

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
                in ptree.session.models.Session.objects.filter(hidden=False)]

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

class ParticipantAdmin(admin.ModelAdmin):
    change_list_template = "admin/ptree_change_list.html"


    def link(self, instance):
        url = instance.start_url()
        return new_tab_link(url, 'Link')

    link.short_description = "Start link"
    link.allow_tags = True
    list_filter = [NonHiddenSessionListFilter, 'experiment', 'treatment', 'match']
    list_per_page = 30

    def queryset(self, request):
        qs = super(ParticipantAdmin, self).queryset(request)
        return qs.filter(session__hidden=False)


class MatchAdmin(admin.ModelAdmin):
    change_list_template = "admin/ptree_change_list.html"

    list_filter = [NonHiddenSessionListFilter, 'experiment', 'treatment']
    list_per_page = 30

    def queryset(self, request):
        qs = super(MatchAdmin, self).queryset(request)
        return qs.filter(session__hidden=False)


class TreatmentAdmin(admin.ModelAdmin):
    change_list_template = "admin/ptree_change_list.html"

    def link(self, instance):
        if instance.experiment.session.preassign_matches:
            return 'Not available (--preassign-matches was set)'
        url = instance.start_url()
        return new_tab_link(url, 'Link')

    link.short_description = "Demo link"
    link.allow_tags = True
    list_filter = [NonHiddenSessionListFilter, 'experiment']

    def queryset(self, request):
        qs = super(TreatmentAdmin, self).queryset(request)
        return qs.filter(session__hidden=False)


class ExperimentAdmin(admin.ModelAdmin):
    change_list_template = "admin/ptree_change_list.html"

    def experimenter_input_link(self, instance):
        url = instance.experimenter_input_url()
        return new_tab_link(url, 'Link')

    def queryset(self, request):
        qs = super(ExperimentAdmin, self).queryset(request)
        return qs.filter(session__hidden=False)

    experimenter_input_link.short_description = 'Link for experimenter input during gameplay'
    experimenter_input_link.allow_tags = True
    list_filter = [NonHiddenSessionListFilter]

class SessionParticipantAdmin(admin.ModelAdmin):
    change_list_template = "admin/ptree_change_list.html"

    list_filter = [NonHiddenSessionListFilter]

    readonly_fields = get_readonly_fields(ptree.session.models.SessionParticipant, [])
    list_display = get_list_display(ptree.session.models.SessionParticipant, readonly_fields)

    def start_link(self, instance):
        url = instance.start_url()
        return new_tab_link(url, 'Link')
    start_link.allow_tags = True

    def queryset(self, request):
        qs = super(SessionParticipantAdmin, self).queryset(request)
        return qs.filter(session__hidden=False)

class SessionAdmin(admin.ModelAdmin):
    change_list_template = "admin/ptree_change_list.html"

    def get_urls(self):
        urls = super(SessionAdmin, self).get_urls()
        my_urls = patterns('',
            (r'^(?P<pk>\d+)/payments/$', self.admin_site.admin_view(self.payments)),
            (r'^(?P<pk>\d+)/mturk_snippet/$', self.admin_site.admin_view(self.mturk_snippet)),
            (r'^(?P<pk>\d+)/start_urls/$', self.start_urls),
        )
        return my_urls + urls

    def start_urls(self, request, pk):
        session = self.model.objects.get(pk=pk)

        if request.GET.get(ptree.constants.experimenter_access_code) != session.experimenter_access_code:
            return HttpResponseBadRequest('{} parameter missing or incorrect'.format(ptree.constants.experimenter_access_code))
        participants = session.participants()
        urls = [request.build_absolute_uri(participant.start_url()) for participant in participants]
        return HttpResponse('\n'.join(urls), content_type="text/plain")

    def start_urls_link(self, instance):
        if not instance.first_experiment:
            return 'No experiments in sequence'
        return new_tab_link('{}/start_urls/?{}={}'.format(instance.pk,
                                                          ptree.constants.experimenter_access_code,
                                                          instance.experimenter_access_code), 'Link')

    start_urls_link.short_description = 'Start URLs'
    start_urls_link.allow_tags = True

    def mturk_snippet(self, request, pk):
        session = self.model.objects.get(pk=pk)
        experiment = session.first_experiment
        hit_page_js_url = request.build_absolute_uri(static_template_tag('ptree/js/mturk_hit_page.js'))
        experiment_url = request.build_absolute_uri(experiment.start_url())
        return render_to_response('admin/MTurkSnippet.html',
                                  {'hit_page_js_url': hit_page_js_url,
                                   'experiment_url': experiment_url,},
                                  content_type='text/plain')

    def mturk_snippet_link(self, instance):
        if not instance.first_experiment:
            return 'No experiments in sequence'
        if instance.is_for_mturk:
            return new_tab_link('{}/mturk_snippet/'.format(instance.pk), 'Link')
        else:
            return 'N/A (is_for_mturk = False)'

    mturk_snippet_link.allow_tags = True
    mturk_snippet_link.short_description = "HTML snippet for MTurk HIT page"

    def global_start_link(self, instance):
        if instance.is_for_mturk:
            return 'N/A (is_for_mturk = True)'
        if not instance.first_experiment:
            return 'No experiments in sequence'
        else:
            url = instance.start_url()
            return new_tab_link(url, 'Link')

    global_start_link.allow_tags = True
    global_start_link.short_description = "Global start URL (only if you can't use regular start URLs)"

    def payments(self, request, pk):
        session = self.model.objects.get(pk=pk)
        participants = session.participants()
        total_payments = sum(participant.total_pay() or 0 for participant in session.participants())

        # order by label if they are numbers. or should we always order by label?


        return render_to_response('admin/Payments.html',
                                  {'participants': participants,
                                  'total_payments': currency(total_payments),
                                  'session_code': session.code,
                                  'session_name': session,
                                  'base_pay': currency(session.base_pay),
                                  })

    def payments_link(self, instance):
        if instance.payments_file_is_ready():
            link_text = 'Ready'
        else:
            link_text = 'Incomplete'
        return new_tab_link('{}/payments/'.format(instance.pk), link_text)

    payments_link.short_description = "Payments page"
    payments_link.allow_tags = True

    readonly_fields = get_readonly_fields(ptree.session.models.Session, [])
    list_display = get_list_display(ptree.session.models.Session, readonly_fields)

    list_editable = ['hidden']




