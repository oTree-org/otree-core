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
        return '<a href="{}" target="_blank">{}</a>'.format(instance.start_url(), instance.start_url())

    link.allow_tags = True
    
class PlayerAdmin(admin.ModelAdmin):
    readonly_fields = ('link', 'code')
    list_display = ('code', 'link', 'has_visited')

    def link(self, instance):
        url = '/{}/PickTreatment/?exp={}&player={}'.format(instance.experiment.url_base, instance.experiment.code, instance.code)
        return '<a href="{}" target="_blank">{}</a>'.format(url, url)

    link.short_description = "Give this link to a single user"
    link.allow_tags = True

for game_label in settings.PTREE_EXPERIMENT_APPS:
    module = import_module("{}.models".format(game_label))
    admin.site.register(module.Experiment)
    admin.site.register(module.Treatment, TreatmentAdmin)
    admin.site.register(module.Player, PlayerAdmin)

