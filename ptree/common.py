from collections import OrderedDict
from django.contrib import admin
from django.conf.urls import patterns
from django.shortcuts import render_to_response
import ptree.constants
from django.http import HttpResponse, HttpResponseBadRequest
from urlparse import urljoin

class ParticipantAdmin(admin.ModelAdmin):


    def link(self, instance):
        url = instance.start_url()
        return '<a href="{}" target="_blank">{}</a>'.format(url, 'Link')

    link.short_description = "Participant link"
    link.allow_tags = True
    list_filter = ['match', 'treatment', 'experiment']

class MatchAdmin(admin.ModelAdmin):
    list_filter = ['treatment', 'experiment']

class TreatmentAdmin(admin.ModelAdmin):
    def link(self, instance):
        url = instance.start_url()
        return '<a href="{}" target="_blank">{}</a>'.format(url, 'Link')

    link.short_description = "Demo link"
    link.allow_tags = True
    list_filter = ['experiment']

class ExperimentAdmin(admin.ModelAdmin):
    def start_link(self, instance):
        url = instance.start_url()
        return '<a href="{}" target="_blank">{}</a>'.format(url, 'Link')

    start_link.short_description = "Start link (only if you can't use participant links)"
    start_link.allow_tags = True

    def payments_link(self, instance):
        return '<a href="{}" target="_blank">{}</a>'.format('{}/payments/'.format(instance.pk), 'Link')

    payments_link.short_description = "Payments page"
    payments_link.allow_tags = True

    def start_urls_link(self, instance):
        return '<a href="{}" target="_blank">{}</a>'.format('{}/start_urls/?{}={}'.format(instance.pk,
                                                                                          ptree.constants.experimenter_access_code,
                                                                                          instance.experimenter_access_code), 'Link')

    start_urls_link.short_description = 'Start URLs'
    start_urls_link.allow_tags = True

    def experimenter_input_link(self, instance):
        url = instance.experimenter_input_url()
        return '<a href="{}" target="_blank">{}</a>'.format(url, 'Link')

    experimenter_input_link.short_description = 'Link for experimenter input during gameplay'
    experimenter_input_link.allow_tags = True

    def get_urls(self):
        urls = super(ExperimentAdmin, self).get_urls()
        my_urls = patterns('',
            (r'^(?P<pk>\d+)/payments/$', self.admin_site.admin_view(self.payments)),
            (r'^(?P<pk>\d+)/start_urls/$', self.start_urls),
        )
        return my_urls + urls

    def start_urls(self, request, pk):
        experiment = self.model.objects.get(pk=pk)
        if request.GET.get(ptree.constants.experimenter_access_code) != experiment.experimenter_access_code:
            return HttpResponseBadRequest('{} parameter missing or incorrect'.format(ptree.constants.experimenter_access_code))
        participants = experiment.participants()
        urls = [urljoin(request.META['HTTP_HOST'], participant.start_url()) for participant in participants]
        return HttpResponse('\n'.join(urls), content_type="text/plain")

    def payments(self, request, pk):
        experiment = self.model.objects.get(pk=pk)
        participants = experiment.participants()
        return render_to_response('admin/Payments.html',
                                  {'experiment_name': experiment.name,
                                   'experiment_code': experiment.code,
                                   'participants': participants,
                                   'total_payments': sum(p.total_pay() for p in participants if p.total_pay())})


def remove_duplicates(lst):
    return list(OrderedDict.fromkeys(lst))

def get_list_display(ModelName, readonly_fields, first_fields):
    all_field_names = [field.name for field in ModelName._meta.fields]

    # make sure they're actually in the model.
    first_fields = [f for f in first_fields if f in all_field_names]

    list_display = first_fields + readonly_fields + all_field_names
    return remove_duplicates(list_display)

def get_readonly_fields(fields_common_to_all_models, fields_specific_to_this_subclass):
    return remove_duplicates(fields_common_to_all_models + fields_specific_to_this_subclass)

def get_participant_readonly_fields(fields_specific_to_this_subclass):
    return get_readonly_fields(['link', 'bonus_display'], fields_specific_to_this_subclass)

def get_participant_list_display(Participant, readonly_fields, first_fields=None):
    first_fields = ['__unicode__', 'id', 'experiment', 'treatment', 'match', 'has_visited'] + (first_fields or [])
    return get_list_display(Participant, readonly_fields, first_fields)

def get_match_readonly_fields(fields_specific_to_this_subclass):
    return get_readonly_fields([], fields_specific_to_this_subclass)

def get_match_list_display(Match, readonly_fields, first_fields=None):
    first_fields = ['__unicode__', 'id', 'experiment', 'treatment', 'time_started'] + (first_fields or [])
    return get_list_display(Match, readonly_fields, first_fields)

def get_treatment_readonly_fields(fields_specific_to_this_subclass):
    return get_readonly_fields(['link'], fields_specific_to_this_subclass)

def get_treatment_list_display(Treatment, readonly_fields, first_fields=None):
    first_fields = ['__unicode__', 'id', 'description', 'experiment'] + (first_fields or [])
    return get_list_display(Treatment, readonly_fields, first_fields)

def get_experiment_readonly_fields(fields_specific_to_this_subclass):
    return get_readonly_fields(['start_link', 'start_urls_link', 'experimenter_input_link', 'payments_link'], fields_specific_to_this_subclass)

def get_experiment_list_display(Experiment, readonly_fields, first_fields=None):
    first_fields = ['__unicode__', 'id', 'description'] + (first_fields or [])
    return get_list_display(Experiment, readonly_fields, first_fields)
