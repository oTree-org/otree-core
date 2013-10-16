__doc__ = """See https://docs.djangoproject.com/en/dev/ref/contrib/admin/"""

from django.contrib import admin
from django.conf import settings
from django.utils.importlib import import_module
import ptree.settings

def get_list_display(ModelName, first_fields, readonly_fields):

    first_fields = first_fields or []
    readonly_fields = readonly_fields or []

    all_field_names = [field.name for field in ModelName._meta.fields]

    # make sure they're actually in the model.
    first_fields = [field for field in first_fields if field in all_field_names]

    additional_fields = [field for field in all_field_names if field not in first_fields]
    list_display = first_fields + readonly_fields + additional_fields
    return list_display


def get_match_list_display(Match, first_fields=None, readonly_fields=None):
    first_fields = ['__unicode__', 'id', 'time_started', 'treatment'] + (first_fields or [])
    return get_list_display(Match, first_fields, readonly_fields)

def get_participant_list_display(Match, first_fields=None, readonly_fields=None):
    first_fields = ['__unicode__', 'id', 'match', 'has_visited'] + (first_fields or [])
    readonly_fields = ['link',] + (readonly_fields or [])
    return get_list_display(Match, first_fields, readonly_fields)

def get_treatment_list_display(Match, first_fields=None, readonly_fields=None):
    first_fields = ['__unicode__', 'id', 'description', 'experiment'] + (first_fields or [])
    readonly_fields = ['link',] + (readonly_fields or [])
    return get_list_display(Match, first_fields, readonly_fields)

def get_experiment_list_display(Match, first_fields=None, readonly_fields=None):
    first_fields = ['__unicode__', 'id', 'description'] + (first_fields or [])
    return get_list_display(Match, first_fields, readonly_fields)


class TreatmentAdmin(admin.ModelAdmin):
    readonly_fields = ('code', 'link')
    list_display = ('__unicode__', 'link')

    def link(self, instance):
        url = instance.start_url()
        return '<a href="{}" target="_blank">{}</a>'.format(url, 'Link')

    link.short_description = "Demo link"
    link.allow_tags = True
    
class ParticipantAdmin(admin.ModelAdmin):

    def link(self, instance):
        url = instance.start_url()
        return '<a href="{}" target="_blank">{}</a>'.format(url, 'Link')

    link.short_description = "Participant link"
    link.allow_tags = True

class MatchAdmin(admin.ModelAdmin):
    pass

class ExperimentAdmin(admin.ModelAdmin):
    pass