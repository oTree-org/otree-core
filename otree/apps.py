from django.apps import AppConfig
from django.utils.translation import ugettext_lazy as _


class OtreeConfig(AppConfig):
    name = 'otree'
    verbose_name = _("Otree")

    def ready(self):
        pass
