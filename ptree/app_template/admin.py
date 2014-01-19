from django.contrib import admin
import {{ app_name }}.models as models
import ptree.adminlib as adminlib

class ParticipantAdmin(adminlib.ParticipantAdmin):
    readonly_fields = adminlib.get_readonly_fields(models.Participant)
    list_display = adminlib.get_list_display(models.Participant, readonly_fields)

class MatchAdmin(adminlib.MatchAdmin):
    readonly_fields = adminlib.get_readonly_fields(models.Match)
    list_display = adminlib.get_list_display(models.Match, readonly_fields)

class TreatmentAdmin(adminlib.TreatmentAdmin):
    readonly_fields = adminlib.get_readonly_fields(models.Treatment)
    list_display = adminlib.get_list_display(models.Treatment, readonly_fields)

class ExperimentAdmin(adminlib.ExperimentAdmin):
    readonly_fields = adminlib.get_readonly_fields(models.Experiment)
    list_display = adminlib.get_list_display(models.Experiment, readonly_fields)

admin.site.register(models.Participant, ParticipantAdmin)
admin.site.register(models.Match, MatchAdmin)
admin.site.register(models.Treatment, TreatmentAdmin)
admin.site.register(models.Experiment, ExperimentAdmin)
