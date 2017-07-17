# -*- coding: utf-8 -*-
from __future__ import division, absolute_import
from . import models
from otree.api import WaitPage
from tests.utils import BlankTemplatePage as Page
from .models import Constants


class Page1(Page):
    def is_displayed(self):
        return False


page_sequence = [
    Page1
]
