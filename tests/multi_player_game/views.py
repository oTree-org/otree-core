# -*- coding: utf-8 -*-
from __future__ import division
from ._builtin import Page, WaitPage
from .models import Constants
import random


class Page(Page):
    template_name = 'multi_player_game/EveryPage.html'


class FieldOnOtherPlayer(Page):

    def is_displayed(self):
        return self.player.id_in_group == 1

    def before_next_page(self):
        for p in self.group.get_players():
            p.from_other_player = 1
        in_all_rounds = self.player.in_all_rounds()
        assert ([p.subsession.round_number for p in in_all_rounds] ==
                range(1, self.subsession.round_number + 1))
        assert in_all_rounds[-1].from_other_player == 1


class PickWinner(WaitPage):

    def after_all_players_arrive(self):
        # testing that this code only gets executed once
        winner = random.choice(self.group.get_players())
        winner.is_winner = True


class ResultsWaitPage(WaitPage):

    def after_all_players_arrive(self):
        self.group.set_payoffs()

        if self.subsession.round_number == Constants.num_rounds:
            this_group_players = self.group.get_players()
            participants = set(
                p.participant for p in this_group_players
            )

            for i, group in enumerate(self.group.in_previous_rounds()):
                assert group.subsession.round_number == i + 1
                players = group.get_players()
                assert len(players) == len(this_group_players)

                assert all(
                    p.participant in participants
                    for p in players
                )


class AllGroupsWaitPage(WaitPage):
    wait_for_all_groups = True

    def after_all_players_arrive(self):

        # TODO: shuffle groups

        for p in self.subsession.get_players():
            p.in_all_groups_wait_page = 5.0
        for g in self.subsession.get_groups():
            g.in_all_groups_wait_page = 5.0


class Results(Page):

    def vars_for_template(self):
        assert self.player.from_other_player == 1
        assert self.player.in_all_groups_wait_page == 5.0
        assert self.group.in_all_groups_wait_page == 5.0

page_sequence = [
    FieldOnOtherPlayer,
    PickWinner,
    ResultsWaitPage,
    AllGroupsWaitPage,
    Results
]
