#!/usr/bin/env python
# -*- coding: utf-8 -*-

from __future__ import absolute_import  # for channels module
import os
import channels.asgi

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "settings")

from otree.common_internal import release_locks
release_locks()

channel_layer = channels.asgi.get_channel_layer()
