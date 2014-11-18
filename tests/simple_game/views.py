# -*- coding: utf-8 -*-
from __future__ import division
from . import models
from ._builtin import Page, WaitPage
from otree.common import Currency, currency_range
from .models import Constants

def variables_for_all_templates(self):
    return {
        # example:
        #'my_field': self.player.my_field,
    }

class MyPage(Page):

    timeout_seconds = 10
    timeout_defaults = {
        'add100_1': 1,
        'add100_2': 99,
    }

    form_model = models.Player
    form_fields = ['add100_1', 'add100_2']

    def participate_condition(self):
        return True

    template_name = 'simple_game/MyPage.html'

    def variables_for_template(self):
        return {
            'my_variable_here': 1,
        }

    def error_message(self, values):
        if values['add100_1'] + values['add100_2'] != 100:
            return 'The numbers must add up to 100'

class ResultsWaitPage(WaitPage):

    def after_all_players_arrive(self):
        self.group.set_payoffs()

class Results(Page):

    template_name = 'simple_game/Results.html'

def pages():
    return [
        MyPage,
        ResultsWaitPage,
        Results
    ]
