#!/usr/bin/env python
# -*- coding: utf-8 -*-

from channels.management.commands.runserver import Command as RunserverCommand

from django.conf import settings
import otree.common_internal


class Command(RunserverCommand):

    def handle(self, *args, **options):
        # clear any room visit records that didn't get cleared on previous server run
        # e.g. because server was killed before the disconnect consumer get executed
        from otree.models_concrete import ParticipantRoomVisit
        try:
            ParticipantRoomVisit.objects.all().delete()
        except: # e.g. DB not created yet
            # OK to ignore, because we only need to delete if
            # if there are stale ParticipantRoomVisit records
            # in the DB.
            pass
        # use in-memory.
        # this is the simplest way to patch runserver to use in-memory,
        # while still using Redis in production
        settings.CHANNEL_LAYERS['default'] = (
            settings.CHANNEL_LAYERS['inmemory'])

        # so we know not to use Huey
        otree.common_internal.USE_REDIS = False
        super(Command, self).handle(*args, **options)
