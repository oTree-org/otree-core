from django.apps import AppConfig, apps
from django.conf import settings
from django.db.models import signals
from django.utils.translation import ugettext_lazy as _
from .management import create_default_superuser, create_singleton_objects


class OtreeConfig(AppConfig):
    name = 'otree'
    label = 'otree'
    verbose_name = _("Otree")

    def setup_create_default_superuser(self):
        authconfig = apps.get_app_config('auth')
        signals.post_migrate.connect(
            create_default_superuser,
            sender=authconfig,
            dispatch_uid='common.models.create_testuser'
        )

    def setup_create_singleton_objects(self):
        signals.post_migrate.connect(create_singleton_objects)

    def ready(self):
        self.setup_create_singleton_objects()
        if getattr(settings, 'CREATE_DEFAULT_SUPERUSER', False):
            self.setup_create_default_superuser()
