import logging
from django.apps import apps
from django.conf import settings
from otree.session.models import StubModel, GlobalSingleton


logger = logging.getLogger('otree')


def create_default_superuser(sender, **kwargs):
    """
    Creates our default superuser.
    """
    User = apps.get_model('auth.User')
    username = settings.ADMIN_USERNAME
    password = settings.ADMIN_PASSWORD
    email = getattr(settings, 'ADMIN_EMAIL', '')
    if not User.objects.filter(username=username).exists():
        logger.info(
            'Creating default superuser. '
            'Username: {} Email: {}'.format(username, email))
        assert User.objects.create_superuser(username, email, password)
    else:
        logger.debug('Default superuser already exists.')


def create_singleton_objects(sender, **kwargs):
    for ModelClass in [StubModel, GlobalSingleton]:
        # if it doesn't already exist, create one.
        ModelClass.objects.get_or_create()
