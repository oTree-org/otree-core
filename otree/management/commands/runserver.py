#!/usr/bin/env python
# -*- coding: utf-8 -*-

from channels.management.commands.runserver import Command as BaseCommand

from django.conf import settings

import otree.common_internal


class Command(BaseCommand):

    def handle(self, *args, **options):
        # clear any room visit records that didn't get cleared on previous server run
        # e.g. because server was killed before the disconnect consumer get executed
        from otree.models_concrete import ParticipantRoomVisit
        ParticipantRoomVisit.objects.all().delete()
        # use in-memory.
        # this is the simplest way to patch runserver to use in-memory,
        # while still using Redis in production
        settings.CHANNEL_LAYERS['default'] = (
            settings.CHANNEL_LAYERS['inmemory'])

        # so we know not to use Huey
        otree.common_internal.USE_REDIS = False
        super(Command, self).handle(*args, **options)
