#!/usr/bin/env python
# -*- coding: utf-8 -*-

import logging
from importlib import import_module

from django.apps import AppConfig, apps
from django.conf import settings
from django.db.models import signals

from otree.models_concrete import StubModel
from otree.models.session import GlobalSingleton


logger = logging.getLogger('otree')
import_module('otree.checks')  # this made that style check work


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
        assert User.objects.create_superuser(username, email='',
                                             password=password)
    else:
        logger.debug('Default superuser already exists.')


def create_singleton_objects(sender, **kwargs):
    for ModelClass in [StubModel, GlobalSingleton]:
        # if it doesn't already exist, create one.
        ModelClass.objects.get_or_create()


class OtreeConfig(AppConfig):
    name = 'otree'
    label = 'otree'
    verbose_name = "oTree"

    def setup_create_default_superuser(self):
        authconfig = apps.get_app_config('auth')
        signals.post_migrate.connect(
            create_default_superuser,
            sender=authconfig,
            dispatch_uid='common.models.create_testuser'
        )

    def setup_create_singleton_objects(self):
        signals.post_migrate.connect(create_singleton_objects)

    def init_celery(self):
        # Load the celery config so that the tasks are picked up correctly.
        from otree.celery.setup import load_celery_app
        load_celery_app()

    def ready(self):
        self.setup_create_singleton_objects()
        if getattr(settings, 'CREATE_DEFAULT_SUPERUSER', False):
            self.setup_create_default_superuser()

        self.init_celery()
