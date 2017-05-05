# -*- coding: utf-8 -*-
from __future__ import division, absolute_import
from . import views
from .models import Constants
from otree.api import Bot

class GBATMixin:
    def assert_same_group_members_in_all_rounds(self):
        if self.player.id_in_group == 1 and self.subsession.round_number == Constants.num_rounds:
            id_lists = []
            for group in self.group.in_all_rounds():
                participant_ids = list(group.player_set.values_list(
                    'participant_id', flat=True))
                id_lists.append(participant_ids)
            assert [id_list == id_lists[0] for id_list in id_lists]

    def assert_no_empty_groups(self):
        num_players = self.subsession.player_set.count()
        if self.player.id_in_subsession == num_players:
            num_groups_without_players = type(self.group).objects.filter(player__isnull=True).count()
            assert num_groups_without_players == 0

    def assert_same_id_in_group_in_all_rounds(self):
        if self.player.round_number == Constants.num_rounds:
            ids_in_group = [p.id_in_group for p in self.player.in_all_rounds()]
            assert all(id_in_group == ids_in_group[0] for id_in_group in ids_in_group)

    def run_assertions(self):
        self.assert_same_group_members_in_all_rounds()
        self.assert_no_empty_groups()
        self.assert_same_id_in_group_in_all_rounds()

class PlayerBot(Bot, GBATMixin):

    def play_round(self):
        assert len(self.group.get_players()) == 2
        yield views.Page1

        self.run_assertions()

