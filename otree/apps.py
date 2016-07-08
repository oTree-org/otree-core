#!/usr/bin/env python
# -*- coding: utf-8 -*-

import logging
from importlib import import_module

from django.apps import AppConfig, apps
from django.conf import settings
from django.db.models import signals

from otree.models_concrete import UndefinedFormModel, GlobalLockModel
import otree
from otree.common_internal import ensure_superuser_exists

logger = logging.getLogger('otree')
import_module('otree.checks')   # this made that style check work


def create_singleton_objects(sender, **kwargs):
    for ModelClass in (UndefinedFormModel, GlobalLockModel):
        # if it doesn't already exist, create one.
        ModelClass.objects.get_or_create()


class OtreeConfig(AppConfig):
    name = 'otree'
    label = 'otree'
    verbose_name = "oTree"

    def setup_create_default_superuser(self):
        authconfig = apps.get_app_config('auth')
        signals.post_migrate.connect(
            ensure_superuser_exists,
            sender=authconfig,
            dispatch_uid='common.models.create_testuser'
        )

    def setup_create_singleton_objects(self):
        signals.post_migrate.connect(create_singleton_objects)

    def ready(self):
        self.setup_create_singleton_objects()
        if getattr(settings, 'CREATE_DEFAULT_SUPERUSER', False):
            self.setup_create_default_superuser()
        # patch settings with info that is only available
        # after other settings loaded
        if hasattr(settings, 'RAVEN_CONFIG'):
            settings.RAVEN_CONFIG['release'] = '{}{}'.format(
                otree.get_version(),
                # need to pass the server if it's DEBUG
                # mode. could do this in extra context or tags,
                # but this seems the most straightforward way
                ',dbg' if settings.DEBUG else ''
            )
