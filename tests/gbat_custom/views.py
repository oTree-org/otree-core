# -*- coding: utf-8 -*-
from __future__ import division, absolute_import
from . import models
from otree.api import WaitPage
from tests.utils import BlankTemplatePage as Page
from .models import Constants


class MyWait(WaitPage):
    group_by_arrival_time = True

    def get_players_for_group(self, waiting_players):
        a_players = [p for p in waiting_players if p.type == 'A']
        b_players = [p for p in waiting_players if p.type == 'B']

        new_group = a_players[:1] + b_players[:1]
        if len(new_group) == 2:
            return new_group

    def is_displayed(self):
        return self.round_number == 1

class Page1(Page):
    pass


page_sequence = [
    MyWait,
    Page1,
]
