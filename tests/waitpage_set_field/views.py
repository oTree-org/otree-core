# -*- coding: utf-8 -*-
from __future__ import division, absolute_import
from . import models
from otree.api import WaitPage
from tests.utils import BlankTemplatePage as Page
from .models import Constants


class MyWait(WaitPage):
    def after_all_players_arrive(self):
        for p in self.group.get_players():
            p.set_to_false = False


class ShouldBeSkipped(Page):
    def is_displayed(self):
        return self.player.set_to_false

    def vars_for_template(self):
        1/0 # this should not be executed


class Page2(Page):
    pass

page_sequence = [
    MyWait,
    ShouldBeSkipped,
    Page2
]
