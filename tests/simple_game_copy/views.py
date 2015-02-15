# -*- coding: utf-8 -*-
from __future__ import division
from . import models
from ._builtin import Page, WaitPage
from otree.common import Currency, currency_range
from .models import Constants

def vars_for_all_templates(self):
    return {
        # example:
        #'my_field': self.player.my_field,
    }

class MyPage(Page):

    form_model = models.Player
    form_fields = ['add100_1', 'add100_2']

    timeout_seconds = 10
    auto_submit_values = {
        'add100_1': 1,
        'add100_2': 99,
    }


    def is_displayed(self):
        return True

    template_name = 'simple_game_copy/MyPage.html'

    def vars_for_template(self):
        return {
            'my_variable_here': 1,
        }

    def error_message(self, values):
        if values['add100_1'] + values['add100_2'] != 100:
            return 'The numbers must add up to 100'

    def after_next_button(self):
        self.player.after_next_button_field = True

class ResultsWaitPage(WaitPage):

    def after_all_players_arrive(self):
        self.group.set_payoffs()

class Results(Page):

    template_name = 'simple_game_copy/Results.html'

page_sequence = [
        MyPage,
        ResultsWaitPage,
        Results
    ]
