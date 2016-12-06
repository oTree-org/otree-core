# -*- coding: utf-8 -*-
from __future__ import division, absolute_import
from . import views
from .models import Constants
from otree.api import Bot


class PlayerBot(Bot):

    def play_round(self):
        # add these in later
        assert self.group.set_in_wait_page == True, self.group.id
        assert self.player.set_in_wait_page == True

        yield views.Page1

        # Race condition: this might be evaluated before all players finish
        # currently it works, but if i change the order that bots run,
        # it might not work in the future.
        # for now, this is the simplest way to get it working with browser bots
        # because there is no validate_play method. (usually its not needed)
        num_players = self.subsession.player_set.count()
        if self.player.id_in_subsession == num_players and self.subsession.round_number == Constants.num_rounds:
            for subsession in self.subsession.in_all_rounds():
                groups = subsession.get_groups()
                players = subsession.get_players()

                print(subsession.get_group_matrix())
                for group in groups:
                    assert len(group.get_players()) == Constants.players_per_group, self.subsession.round_number
                assert len(groups) == len(players) / Constants.players_per_group

