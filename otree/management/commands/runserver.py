#!/usr/bin/env python
# -*- coding: utf-8 -*-

from channels.management.commands.runserver import Command as RunserverCommand

from django.conf import settings
import otree.common_internal


class Command(RunserverCommand):

    def handle(self, *args, **options):
        # use in-memory.
        # this is the simplest way to patch runserver to use in-memory,
        # while still using Redis in production
        settings.CHANNEL_LAYERS['default'] = (
            settings.CHANNEL_LAYERS['inmemory'])

        # don't use cached template loader, so that users can refresh files
        # and see the update.
        # kind of a hack to patch it here and to refer it as [0],
        # but can't think of a better way.
        settings.TEMPLATES[0]['OPTIONS']['loaders'] = {
            'django.template.loaders.filesystem.Loader',
            'django.template.loaders.app_directories.Loader',
        }

        # so we know not to use Huey
        otree.common_internal.USE_REDIS = False
        super(Command, self).handle(*args, **options)
