# -*- coding: utf-8 -*-
from __future__ import division
from . import models
from ._builtin import Page, WaitPage
from otree.common import Currency, currency_range
from .models import Constants

class MyPage(Page):

    form_model = models.Player

class ResultsWaitPage(WaitPage):

    def after_all_players_arrive(self):
        self.group.set_payoffs()

class Results(Page):
    pass

page_sequence = [
        MyPage,
        ResultsWaitPage,
        Results
    ]
