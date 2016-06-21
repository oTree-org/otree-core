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

        # so we know not to use Huey
        otree.common_internal.USE_REDIS = False
        super(Command, self).handle(*args, **options)
