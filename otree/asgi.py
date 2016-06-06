#!/usr/bin/env python
# -*- coding: utf-8 -*-

from __future__ import absolute_import  # for channels module
import os
import channels.asgi

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "settings")

from otree.models_concrete import ParticipantRoomVisit


try:
    ParticipantRoomVisit.objects.all().delete()
except:  # e.g. DB not created yet
    # OK to ignore, because we only need to delete if
    # if there are stale ParticipantRoomVisit records
    # in the DB.
    pass

channel_layer = channels.asgi.get_channel_layer()
