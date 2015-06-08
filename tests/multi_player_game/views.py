# -*- coding: utf-8 -*-
from __future__ import division
from . import models
from ._builtin import Page, WaitPage


class Page(Page):
    template_name = 'multi_player_game/EveryPage.html'


class FieldOnOtherPlayer(Page):

    form_model = models.Player

    def is_displayed(self):
        return self.player.id_in_group == 1

    def before_next_page(self):
        for p in self.group.get_players():
            p.from_other_player = 1
        in_all_rounds = self.player.in_all_rounds()
        assert len(in_all_rounds) == self.subsession.round_number
        assert ([p.subsession.round_number for p in in_all_rounds] ==
                range(1, self.subsession.round_number + 1))
        assert in_all_rounds[-1].from_other_player == 1


class ResultsWaitPage(WaitPage):

    def after_all_players_arrive(self):
        self.group.set_payoffs()


class Results(Page):

    def vars_for_template(self):
        assert self.player.from_other_player == 1


page_sequence = [
    FieldOnOtherPlayer,
    ResultsWaitPage,
    Results
]
