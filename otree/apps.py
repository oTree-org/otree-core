from django.apps import AppConfig, apps
from django.conf import settings
from django.db.models import signals
from django.utils.translation import ugettext_lazy as _
from . import checks
import logging

logger = logging.getLogger('otree')

from otree.session.models import StubModel, GlobalSingleton

def create_default_superuser(sender, **kwargs):
    """
    Creates our default superuser.
    """
    User = apps.get_model('auth.User')
    username = settings.ADMIN_USERNAME
    password = settings.ADMIN_PASSWORD
    if not User.objects.filter(username=username).exists():
        logger.info(
            'Creating default superuser. '
            'Username: {}'.format(username))
        assert User.objects.create_superuser(username, email='', password=password)
    else:
        logger.debug('Default superuser already exists.')


def create_singleton_objects(sender, **kwargs):
    for ModelClass in [StubModel, GlobalSingleton]:
        # if it doesn't already exist, create one.
        ModelClass.objects.get_or_create()


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
