# -*- coding: utf-8 -*-
from __future__ import division, absolute_import
from . import models
from .models import Constants
from otree.api import WaitPage, Currency as c
from tests.utils import BlankTemplatePage as Page


class Start(Page):

    def vars_for_template(self):
        assert self.session.vars['a'] == 1
        assert self.participant.vars['a'] == 1
        assert self.participant.vars['b'] == 1
        assert self.participant.vars['c'] == Constants.complex_data_structure
        assert self.session.config['treatment'] == 'blue'

        assert self.player.in_creating_session == 1
        assert self.group.in_creating_session == 1

        return {
            'my_variable_here': 1,
        }

    def before_next_page(self):
        self.player.after_next_button_field = True
        self.session.vars['a'] = 2


class IsDisplayed(Page):

    def is_displayed(self):
        # make sure it's available during pre-fetch
        # this must be directly after a regular page
        assert self.session
        return True


class ResultsWaitPage(WaitPage):

    def after_all_players_arrive(self):
        assert self.session.vars['a'] == 2
        self.group.set_payoffs()
        for player in self.group.get_players():
            player.participant.vars['a'] = 2


class End(Page):

    def vars_for_template(self):
        assert self.player.after_next_button_field is True
        assert self.player.participant.vars['a'] == 2
        participant = self.player.participant
        assert participant.payoff == 50
        assert participant.payoff_plus_participation_fee() == 50 + 9.99
        return {}


page_sequence = [
    Start,
    IsDisplayed,
    ResultsWaitPage,
    End,
]
