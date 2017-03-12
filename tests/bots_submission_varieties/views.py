# -*- coding: utf-8 -*-
from __future__ import division, absolute_import
from . import models
from otree.api import WaitPage
from tests.utils import BlankTemplatePage as Page
from .models import Constants


class Page1(Page):
    pass


class Page2(Page):
    form_model = models.Player
    form_fields = ['f2']


class Page3(Page):
    form_model = models.Player
    form_fields = ['f3']


page_sequence = [
    Page1, Page2, Page3
]
