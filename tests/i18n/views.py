# -*- coding: utf-8 -*-
from __future__ import division, absolute_import
from . import models
from otree.api import WaitPage, Page
from .models import Constants
from django.conf import settings


class Page1(Page):
    form_model = models.Player
    form_fields = ['contribution', 'yesno']
    timeout_seconds = 60


class MyWait(WaitPage):
    pass


page_sequence = [
    Page1,
    MyWait,
]
