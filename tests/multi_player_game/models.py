# -*- coding: utf-8 -*-
# <standard imports>
from __future__ import division
from otree.db import models
import otree.models
# </standard imports>


class Constants:
    name_in_url = 'multi_player_game'
    players_per_group = 3
    num_rounds = 2


class Subsession(otree.models.BaseSubsession):

    def before_session_starts(self):
        if self.round_number == 2:
            for group in self.get_groups():
                players = group.get_players()
                pks = [p.pk for p in players]
                for i, p in enumerate(players):
                    assert p.id_in_group == i + 1
                players.reverse()
                group.set_players(players)
                pks_reversed = list(reversed(pks))
                assert [p.pk for p in group.get_players()] == pks_reversed


class Group(otree.models.BaseGroup):
    # <built-in>
    subsession = models.ForeignKey(Subsession)
    # </built-in>

    def set_payoffs(self):
        for p in self.get_players():
            p.payoff = 50

    in_all_groups_wait_page = models.FloatField(initial=0)


class Player(otree.models.BasePlayer):
    # <built-in>
    subsession = models.ForeignKey(Subsession)
    group = models.ForeignKey(Group, null=True)
    # </built-in>

    def other_player(self):
        """Returns other player in group. Only valid for 2-player groups."""
        return self.get_others_in_group()[0]

    from_other_player = models.PositiveIntegerField()

    is_winner = models.BooleanField(initial=False)
    in_all_groups_wait_page = models.FloatField(initial=0)

    def role(self):
        # you can make this depend of self.id_in_group
        return ''