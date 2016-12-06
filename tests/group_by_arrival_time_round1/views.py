# -*- coding: utf-8 -*-
from __future__ import division, absolute_import
from . import models
from otree.api import WaitPage
from tests.utils import BlankTemplatePage as Page
from .models import Constants


class MyWait(WaitPage):
    group_by_arrival_time = True

    def is_displayed(self):
        return self.round_number == 1



class Page1(Page):
    pass


page_sequence = [
    MyWait,
    Page1,
]
