from collections import OrderedDict
from django.contrib import admin
from django.conf.urls import patterns
from django.shortcuts import render_to_response
import ptree.constants
from django.http import HttpResponse, HttpResponseBadRequest
from urlparse import urljoin
import datetime
from django.contrib.staticfiles.templatetags.staticfiles import static as static_template_tag
import ptree.stuff.models
from collections import defaultdict

def new_tab_link(url, label):
    return '<a href="{}" target="_blank">{}</a>'.format(url, label)

def start_urls_for_experiment(experiment, request):
    if request.GET.get(ptree.constants.experimenter_access_code) != experiment.experimenter_access_code:
        return HttpResponseBadRequest('{} parameter missing or incorrect'.format(ptree.constants.experimenter_access_code))
    participants = experiment.participants()
    urls = [request.build_absolute_uri(participant.start_url()) for participant in participants]
    return HttpResponse('\n'.join(urls), content_type="text/plain")

class ParticipantAdmin(admin.ModelAdmin):


    def link(self, instance):
        url = instance.start_url()
        return new_tab_link(url, 'Link')

    link.short_description = "Participant link"
    link.allow_tags = True
    list_filter = ['match', 'treatment', 'experiment']

class MatchAdmin(admin.ModelAdmin):
    list_filter = ['treatment', 'experiment']

class TreatmentAdmin(admin.ModelAdmin):
    def link(self, instance):
        url = instance.start_url()
        return new_tab_link(url, 'Link')

    link.short_description = "Demo link"
    link.allow_tags = True
    list_filter = ['experiment']

class ExperimentAdmin(admin.ModelAdmin):
    def global_start_link(self, instance):
        if instance.is_for_mturk:
            return 'N/A (is_for_mturk = True)'
        else:
            url = instance.start_url()
            return new_tab_link(url, 'Link')

    global_start_link.allow_tags = True
    global_start_link.short_description = "Global start URL (only if you can't use regular start URLs)"

    def mturk_snippet_link(self, instance):
        if instance.is_for_mturk:
            return new_tab_link('{}/mturk_snippet/'.format(instance.pk), 'Link')
        else:
            return 'N/A (is_for_mturk = False)'

    mturk_snippet_link.allow_tags = True
    mturk_snippet_link.short_description = "HTML snippet for MTurk HIT page"


    def payments_link(self, instance):
        return new_tab_link('{}/payments/'.format(instance.pk), 'Link')

    payments_link.short_description = "Payments page"
    payments_link.allow_tags = True

    def start_urls_link(self, instance):
        return new_tab_link('{}/start_urls/?{}={}'.format(instance.pk,
                                                          ptree.constants.experimenter_access_code,
                                                          instance.experimenter_access_code), 'Link')

    start_urls_link.short_description = 'Start URLs'
    start_urls_link.allow_tags = True

    def experimenter_input_link(self, instance):
        url = instance.experimenter_input_url()
        return new_tab_link(url, 'Link')

    experimenter_input_link.short_description = 'Link for experimenter input during gameplay'
    experimenter_input_link.allow_tags = True

    def get_urls(self):
        urls = super(ExperimentAdmin, self).get_urls()
        my_urls = patterns('',
            (r'^(?P<pk>\d+)/payments/$', self.admin_site.admin_view(self.payments)),
            (r'^(?P<pk>\d+)/start_urls/$', self.start_urls),
            (r'^(?P<pk>\d+)/mturk_snippet/$', self.admin_site.admin_view(self.mturk_snippet))
        )
        return my_urls + urls

    def start_urls(self, request, pk):
        experiment = self.model.objects.get(pk=pk)
        return start_urls_for_experiment(experiment, request)


    def mturk_snippet(self, request, pk):
        experiment = self.model.objects.get(pk=pk)
        hit_page_js_url = request.build_absolute_uri(static_template_tag('ptree/js/mturk_hit_page.js'))
        experiment_url = request.build_absolute_uri(experiment.start_url())
        return render_to_response('admin/MTurkSnippet.html',
                                  {'hit_page_js_url': hit_page_js_url,
                                   'experiment_url': experiment_url,},
                                  content_type='text/plain')

    def payments(self, request, pk):
        experiment = self.model.objects.get(pk=pk)
        participants = experiment.participants().order_by('external_id', 'code')
        return render_to_response('admin/Payments.html',
                                  {'app_name': experiment._meta.app_label,
                                   'experiment_name': experiment.name,
                                   'experiment_code': experiment.code,
                                   'participants': participants,
                                   'total_payments': sum(p.total_pay() for p in participants if p.total_pay())})

class ParticipantInSequenceOfExperiments(object):
    def __init__(self, external_id, total_pay):
        self.external_id = external_id
        self.total_pay = total_pay

class SequenceOfExperimentsAdmin(admin.ModelAdmin):

    def get_urls(self):
        urls = super(SequenceOfExperimentsAdmin, self).get_urls()
        my_urls = patterns('',
            (r'^(?P<pk>\d+)/payments/$', self.admin_site.admin_view(self.payments)),
            (r'^(?P<pk>\d+)/start_urls/$', self.start_urls),
        )
        return my_urls + urls


    def start_urls(self, request, pk):
        sequence_of_experiments = self.model.objects.get(pk=pk)
        return start_urls_for_experiment(sequence_of_experiments.first_experiment, request)

    def payments(self, request, pk):
        sequence_of_experiments = self.model.objects.get(pk=pk)

        payments = defaultdict(int)

        experiment = sequence_of_experiments.first_experiment

        while True:
            for participant in experiment.participants():
                payments[participant.external_id] += participant.total_pay()
            experiment = experiment.next_experiment
            if not experiment:
                break

        total_payments = 0
        participants = []
        for k,v in OrderedDict(payments).items():
            total_payments += v
            participants.append(ParticipantInSequenceOfExperiments(k, v))

        return render_to_response('admin/PaymentsForSequenceOfExperiments.html',
                                  {'participants': participants,
                                  'total_payments': total_payments,
                                  'sequence_of_experiments_code': sequence_of_experiments.code,
                                  'sequence_of_experiments_name': sequence_of_experiments.name,
                                  })

    def payments_link(self, instance):
        return new_tab_link('{}/payments/'.format(instance.pk), 'Link')

    payments_link.short_description = "Payments page"
    payments_link.allow_tags = True

    def start_urls_link(self, instance):
        return new_tab_link('{}/start_urls/?{}={}'.format(instance.pk,
                                                          ptree.constants.experimenter_access_code,
                                                          instance.experimenter_access_code), 'Link')

    start_urls_link.short_description = 'Start URLs'
    start_urls_link.allow_tags = True



def remove_duplicates(lst):
    return list(OrderedDict.fromkeys(lst))

def get_list_display(ModelName, readonly_fields, first_fields):
    all_field_names = [field.name for field in ModelName._meta.fields]


    # make sure they're actually in the model.
    #first_fields = [f for f in first_fields if f in all_field_names]

    list_display = first_fields + readonly_fields + all_field_names
    return remove_duplicates(list_display)

def get_readonly_fields(fields_common_to_all_models, fields_specific_to_this_subclass):
    return remove_duplicates(fields_common_to_all_models + fields_specific_to_this_subclass)

def get_participant_readonly_fields(fields_specific_to_this_subclass):
    return get_readonly_fields(['link', 'bonus_display'], fields_specific_to_this_subclass)

def get_participant_list_display(Participant, readonly_fields, first_fields=None):
    first_fields = ['id', 'experiment', 'treatment', 'match', 'has_visited'] + (first_fields or [])
    return get_list_display(Participant, readonly_fields, first_fields)

def get_match_readonly_fields(fields_specific_to_this_subclass):
    return get_readonly_fields([], fields_specific_to_this_subclass)

def get_match_list_display(Match, readonly_fields, first_fields=None):
    first_fields = ['id', 'experiment', 'treatment', 'time_started'] + (first_fields or [])
    return get_list_display(Match, readonly_fields, first_fields)

def get_treatment_readonly_fields(fields_specific_to_this_subclass):
    return get_readonly_fields(['link'], fields_specific_to_this_subclass)

def get_treatment_list_display(Treatment, readonly_fields, first_fields=None):
    first_fields = ['unicode', 'experiment'] + (first_fields or [])
    return get_list_display(Treatment, readonly_fields, first_fields)

def get_experiment_readonly_fields(fields_specific_to_this_subclass):
    return get_readonly_fields(['start_urls_link', 'mturk_snippet_link', 'global_start_link', 'experimenter_input_link', 'payments_link'], fields_specific_to_this_subclass)

def get_experiment_list_display(Experiment, readonly_fields, first_fields=None):
    first_fields = ['unicode'] + (first_fields or [])
    return get_list_display(Experiment, readonly_fields, first_fields)

def get_sequence_of_experiments_readonly_fields(fields_specific_to_this_subclass):
    return get_readonly_fields(['start_urls_link', 'payments_link'], fields_specific_to_this_subclass)

def get_experiment_list_display(Experiment, readonly_fields, first_fields=None):
    first_fields = ['__unicode__', 'id', 'description'] + (first_fields or [])
    return get_list_display(Experiment, readonly_fields, first_fields)


def create_sequence_of_experiments(experiments, name):
    seq = ptree.stuff.models.SequenceOfExperiments(name = name)
    seq.add_experiments(experiments)

