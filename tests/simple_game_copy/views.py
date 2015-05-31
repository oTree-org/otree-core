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
    form_fields = [
        'add100_1',
        'add100_2',
        #'value_for_both_players'
    ]

    timeout_seconds = 10
    timeout_submission = {
        'add100_1': 1,
        'add100_2': 99,
    }


    def is_displayed(self):
        return True

    def vars_for_template(self):
        return {
            'my_variable_here': 1,
        }

    def error_message(self, values):
        if values['add100_1'] + values['add100_2'] != 100:
            return 'The numbers must add up to 100'

    def before_next_page(self):
        self.player.after_next_button_field = True

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
