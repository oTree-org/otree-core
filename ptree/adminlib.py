from collections import OrderedDict
from django.contrib import admin
from django.conf.urls import patterns
from django.shortcuts import render_to_response
import ptree.constants
from django.http import HttpResponse, HttpResponseBadRequest
from django.contrib.staticfiles.templatetags.staticfiles import static as static_template_tag
import ptree.sequence_of_experiments.models
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

def get_list_display(ModelName, readonly_fields, first_fields, exclude_fields):
    all_field_names = [field.name for field in ModelName._meta.fields if field.name not in exclude_fields]


    # make sure they're actually in the model.
    #first_fields = [f for f in first_fields if f in all_field_names]

    list_display = first_fields + readonly_fields + all_field_names
    return remove_duplicates(list_display)

def get_readonly_fields(fields_common_to_all_models, fields_specific_to_this_subclass):
    return remove_duplicates(fields_common_to_all_models + fields_specific_to_this_subclass)

def get_participant_readonly_fields(fields_specific_to_this_subclass):
    return get_readonly_fields(['name',
                                'link',
                                'bonus_display',
                                'progress'],
                               fields_specific_to_this_subclass)

def get_participant_list_display(Participant, readonly_fields, first_fields=None):
    first_fields = ['name',
                    'sequence_of_experiments',
                    'experiment',
                    'treatment',
                    'match',
                    'visited',
                    'progress'] + (first_fields or [])
    exclude_fields = ['id',
                      'code',
                      'index_in_sequence_of_views',
                      'me_in_previous_experiment_content_type',
                      'me_in_previous_experiment_object_id',
                      'me_in_next_experiment_content_type',
                      'me_in_next_experiment_object_id',
                      'participant_in_sequence_of_experiments',
                      ]

    return get_list_display(Participant, readonly_fields, first_fields, exclude_fields)

def get_match_readonly_fields(fields_specific_to_this_subclass):
    return get_readonly_fields([], fields_specific_to_this_subclass)

def get_match_list_display(Match, readonly_fields, first_fields=None):
    first_fields = ['id',
                    'sequence_of_experiments',
                    'experiment',
                    'treatment'] + (first_fields or [])
    fields_to_exclude = []
    return get_list_display(Match, readonly_fields, first_fields, fields_to_exclude)

def get_treatment_readonly_fields(fields_specific_to_this_subclass):
    return get_readonly_fields(['link'], fields_specific_to_this_subclass)

def get_treatment_list_display(Treatment, readonly_fields, first_fields=None):
    first_fields = ['name',
                    'sequence_of_experiments',
                    'experiment'] + (first_fields or [])
    fields_to_exclude = ['id', 'label']
    return get_list_display(Treatment, readonly_fields, first_fields, fields_to_exclude)

def get_experiment_readonly_fields(fields_specific_to_this_subclass):
    return get_readonly_fields(['experimenter_input_link'], fields_specific_to_this_subclass)

def get_experiment_list_display(Experiment, readonly_fields, first_fields=None):
    first_fields = ['name', 'sequence_of_experiments'] + (first_fields or [])
    fields_to_exclude = ['id',
                         'label',
                         'sequence_of_experiments_access_code',
                         'next_experiment_content_type',
                         'next_experiment_object_id',
                         'next_experiment',
                         'previous_experiment_content_type',
                         'previous_experiment_object_id',
                         'previous_experiment',
                         'experimenter_access_code',
                         ]
    return get_list_display(Experiment, readonly_fields, first_fields, fields_to_exclude)

def get_sequence_of_experiments_readonly_fields(fields_specific_to_this_subclass):
    return get_readonly_fields(['experiment_names',
                                'start_urls_link',
                                'global_start_link',
                                'mturk_snippet_link',
                                'payments_link'], fields_specific_to_this_subclass)

def get_sequence_of_experiments_list_display(SequenceOfExperiments, readonly_fields, first_fields=None):
    first_fields = ['name'] + (first_fields or [])
    fields_to_exclude = ['id',
                         'label',
                         'first_experiment_content_type',
                         'first_experiment_object_id',
                         'first_experiment']
    return get_list_display(SequenceOfExperiments, readonly_fields, first_fields, fields_to_exclude)

def get_participant_in_sequence_of_experiments_readonly_fields(fields_specific_to_this_subclass):
    return get_readonly_fields(['bonus_display', 'start_link', 'progress'], fields_specific_to_this_subclass)

def get_participant_in_sequence_of_experiments_list_display(Participant, readonly_fields, first_fields=None):
    first_fields = ['name', 'progress'] + (first_fields or [])
    fields_to_exclude = ['id',
                         'index_in_sequence_of_experiments',
                         'label',
                         'me_in_first_experiment_content_type',
                         'me_in_first_experiment_object_id']

    return get_list_display(Participant, readonly_fields, first_fields, fields_to_exclude)


class ParticipantAdmin(admin.ModelAdmin):
    change_list_template = "admin/ptree_change_list.html"


    def link(self, instance):
        url = instance.start_url()
        return new_tab_link(url, 'Link')

    link.short_description = "Start link"
    link.allow_tags = True
    list_filter = ['sequence_of_experiments', 'experiment', 'treatment', 'match']
    list_per_page = 30

class MatchAdmin(admin.ModelAdmin):
    change_list_template = "admin/ptree_change_list.html"

    list_filter = ['sequence_of_experiments', 'experiment', 'treatment']
    list_per_page = 30

class TreatmentAdmin(admin.ModelAdmin):
    change_list_template = "admin/ptree_change_list.html"

    def link(self, instance):
        if instance.experiment.sequence_of_experiments.preassign_matches:
            return 'Not available (--preassign-matches was set)'
        url = instance.start_url()
        return new_tab_link(url, 'Link')

    link.short_description = "Demo link"
    link.allow_tags = True
    list_filter = ['sequence_of_experiments', 'experiment']

class ExperimentAdmin(admin.ModelAdmin):
    change_list_template = "admin/ptree_change_list.html"

    def experimenter_input_link(self, instance):
        url = instance.experimenter_input_url()
        return new_tab_link(url, 'Link')

    experimenter_input_link.short_description = 'Link for experimenter input during gameplay'
    experimenter_input_link.allow_tags = True
    list_filter = ['sequence_of_experiments']

class ParticipantInSequenceOfExperimentsAdmin(admin.ModelAdmin):
    change_list_template = "admin/ptree_change_list.html"

    list_filter = ['sequence_of_experiments']

    readonly_fields = get_participant_in_sequence_of_experiments_readonly_fields([])
    list_display = get_participant_in_sequence_of_experiments_list_display(ptree.sequence_of_experiments.models.Participant,
                                                                           readonly_fields=readonly_fields)

    def start_link(self, instance):
        url = instance.start_url()
        return new_tab_link(url, 'Link')
    start_link.allow_tags = True



class SequenceOfExperimentsAdmin(admin.ModelAdmin):
    change_list_template = "admin/ptree_change_list.html"

    def get_urls(self):
        urls = super(SequenceOfExperimentsAdmin, self).get_urls()
        my_urls = patterns('',
            (r'^(?P<pk>\d+)/payments/$', self.admin_site.admin_view(self.payments)),
            (r'^(?P<pk>\d+)/mturk_snippet/$', self.admin_site.admin_view(self.mturk_snippet)),
            (r'^(?P<pk>\d+)/start_urls/$', self.start_urls),
        )
        return my_urls + urls

    def start_urls(self, request, pk):
        sequence_of_experiments = self.model.objects.get(pk=pk)

        if request.GET.get(ptree.constants.experimenter_access_code) != sequence_of_experiments.experimenter_access_code:
            return HttpResponseBadRequest('{} parameter missing or incorrect'.format(ptree.constants.experimenter_access_code))
        participants = sequence_of_experiments.participants()
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
        sequence_of_experiments = self.model.objects.get(pk=pk)
        experiment = sequence_of_experiments.first_experiment
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
        sequence_of_experiments = self.model.objects.get(pk=pk)
        participants = sequence_of_experiments.participants()
        total_payments = sum(participant.total_pay() or 0 for participant in sequence_of_experiments.participants())


        return render_to_response('admin/Payments.html',
                                  {'participants': participants,
                                  'total_payments': currency(total_payments),
                                  'sequence_of_experiments_code': sequence_of_experiments.code,
                                  'sequence_of_experiments_name': sequence_of_experiments,
                                  'base_pay': currency(sequence_of_experiments.base_pay),
                                  })

    def payments_link(self, instance):
        if instance.payments_file_is_ready():
            link_text = 'Ready'
        else:
            link_text = 'Not ready'
        return new_tab_link('{}/payments/'.format(instance.pk), link_text)

    payments_link.short_description = "Payments page"
    payments_link.allow_tags = True

    readonly_fields = get_sequence_of_experiments_readonly_fields([])
    list_display = get_sequence_of_experiments_list_display(ptree.sequence_of_experiments.models.SequenceOfExperiments,
                                        readonly_fields=readonly_fields)





