# -*- coding: utf-8 -*-
from __future__ import division, absolute_import
from . import models
from otree.api import WaitPage, Page
from .models import Constants


class Page1(Page):
    pass


page_sequence = [Page1]
