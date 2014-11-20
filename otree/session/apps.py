from django.apps import AppConfig
from django.utils.translation import ugettext_lazy as _


class OtreeSessionConfig(AppConfig):
    name = 'otree.session'
    label = 'session'
    verbose_name = _('Otree Sessions')
