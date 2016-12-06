# -*- coding: utf-8 -*-
from __future__ import division, absolute_import
from . import models
from otree.api import WaitPage
from tests.utils import BlankTemplatePage as Page
from .models import Constants


class MyWait(WaitPage):
    group_by_arrival_time = True

    def after_all_players_arrive(self):
        self.group.set_in_wait_page = True
        for p in self.group.get_players():
            p.set_in_wait_page = True


class Page1(Page):

    def before_next_page(self):
        players_in_group = len(self.group.get_players())
        assert players_in_group == Constants.players_per_group, [self.subsession.round_number, self.player.id_in_subsession]


page_sequence = [
    MyWait,
    Page1,
]
