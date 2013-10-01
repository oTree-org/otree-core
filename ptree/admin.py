__doc__ = """See https://docs.djangoproject.com/en/dev/ref/contrib/admin/"""

from django.contrib import admin
from django.conf import settings
from donation.models import Experiment

from django.utils.importlib import import_module

# will this work? i think so.
from django.conf import settings

class TreatmentAdmin(admin.ModelAdmin):
    readonly_fields = ('link', 'code')

    def link(self, instance):
        url = instance.start_url(demo_mode = True)
        return '<a href="{}" target="_blank">{}</a>'.format(instance.start_url(), instance.start_url())

    link.short_description = "Click link to try this treatment in demo mode"
    link.allow_tags = True
    
class ParticipantAdmin(admin.ModelAdmin):
    readonly_fields = ('code', 'link',)
    list_display = readonly_fields + ('has_visited',)

    def link(self, instance):
        url = instance.start_url()
        return '<a href="{}" target="_blank">{}</a>'.format(url, url)

    link.short_description = "Give this link to a single user"
    link.allow_tags = True

for game_label in settings.PTREE_EXPERIMENT_APPS:
    module = import_module("{}.models".format(game_label))
    admin.site.register(module.Experiment)
    admin.site.register(module.Treatment, TreatmentAdmin)
    admin.site.register(module.Participant, ParticipantAdmin)

