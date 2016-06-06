#!/usr/bin/env python
# -*- coding: utf-8 -*-

from __future__ import absolute_import  # for channels module
import os
import channels.asgi

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "settings")

from otree.models_concrete import ParticipantRoomVisit
ParticipantRoomVisit.objects.all().delete()

channel_layer = channels.asgi.get_channel_layer()
