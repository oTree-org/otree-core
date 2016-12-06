# -*- coding: utf-8 -*-
from __future__ import division, absolute_import
from . import views
from .models import Constants
from otree.api import Bot


class PlayerBot(Bot):

    def play_round(self):
        assert len(self.group.get_players()) == 2
        yield views.Page1

        if self.player.id_in_group == 1 and self.subsession.round_number == Constants.num_rounds:
            id_lists = []
            for group in self.group.in_all_rounds():
                participant_ids = list(group.player_set.values_list(
                    'participant_id', flat=True))
                id_lists.append(participant_ids)
            assert [id_list == id_lists[0] for id_list in id_lists]
        num_players = self.subsession.player_set.count()
        if self.player.id_in_subsession == num_players:
            num_groups_with_players = type(self.player).objects.filter(
                    subsession=self.subsession
                ).values_list('group_id', flat=True).distinct().count()
            num_groups = type(self.group).objects.filter(
                    subsession=self.subsession
            ).count()

            assert num_groups_with_players == num_groups
        if self.player.round_number == Constants.num_rounds:
            ids_in_group = [p.id_in_group for p in self.player.in_all_rounds()]
            assert all(id_in_group == ids_in_group[0] for id_in_group in ids_in_group)
