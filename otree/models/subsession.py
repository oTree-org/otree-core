#!/usr/bin/env python
# -*- coding: utf-8 -*-

from __future__ import division

from django.db.models import Case, When, Value, Prefetch
import six
from six.moves import zip

from otree_save_the_change.mixins import SaveTheChange
from otree.db import models
from otree.common_internal import get_models_module
from otree import match_players


class BaseSubsession(SaveTheChange, models.Model):
    """Base class for all Subsessions.

    """

    class Meta:
        abstract = True
        index_together = ['session', 'round_number']

    def in_rounds(self, first, last):
        qs = type(self).objects.filter(
            session=self.session,
            round_number__range=(first, last),
        ).order_by('round_number')

        return list(qs)

    def in_previous_rounds(self):
        return self.in_rounds(1, self.round_number-1)

    def in_all_rounds(self):
        return self.in_previous_rounds() + [self]

    def name(self):
        return str(self.pk)

    def __unicode__(self):
        return self.name()

    def in_round(self, round_number):
        return type(self).objects.get(
            session=self.session,
            round_number=round_number
        )

    def _get_players_per_group_list(self):
        """get a list whose elements are the number of players in each group

        Example: a group of 30 players

        # everyone is in the same group
        [30]

        # 5 groups of 6
        [6, 6, 6, 6, 6,]

        # 2 groups of 5 players, 2 groups of 10 players
        [5, 10, 5, 10] # (you can do this with players_per_group = [5, 10]

        """

        ppg = self._Constants.players_per_group
        subsession_size = self.player_set.count()
        if ppg is None:
            return [subsession_size]

        # if groups have variable sizes, you can put it in a list
        if isinstance(ppg, (list, tuple)):
            assert all(n > 1 for n in ppg)
            group_cycle = ppg
        else:
            assert isinstance(ppg, six.integer_types) and ppg > 1
            group_cycle = [ppg]

        num_group_cycles = subsession_size // sum(group_cycle)
        return group_cycle * num_group_cycles

    def get_groups(self):
        return list(self.group_set.order_by('id_in_subsession'))

    def get_players(self):
        return list(self.player_set.order_by('pk'))

    def get_grouped_players(self):
        players_prefetch = Prefetch(
            'player_set',
            queryset=self._PlayerClass().objects.order_by('id_in_group'),
            to_attr='_ordered_players')
        return [group._ordered_players
                for group in self.group_set.order_by('id_in_subsession')
                                 .prefetch_related(players_prefetch)]

    def check_group_integrity(self):
        '''

        2015-4-17: can't check this from set_players,
        because sometimes we are intentionally in an inconsistent state
        e.g., if group_by_arrival_time is true, and some players have not
        been assigned to groups yet
        '''
        players = self.player_set.values_list('pk', flat=True)
        players_from_groups = self._PlayerClass().objects.filter(
            group__subsession=self).values_list('pk', flat=True)
        assert set(players) == set(players_from_groups)

    def _set_groups(self, groups, check_integrity=True):
        """elements in the list can be sublists, or group objects.

        Maybe this should be re-run after before_session_starts() to ensure
        that id_in_groups are consistent. Or at least we should validate.


        warning: this deletes the groups and any data stored on them
        TODO: we should indicate this in docs
        """

        # first, get players in each group
        matrix = []
        for group in groups:
            if isinstance(group, self._GroupClass()):
                matrix.append(group.get_players())
            else:
                players_list = group
                matrix.append(players_list)
                # assume it's an iterable containing the players
        # Before deleting groups, Need to set the foreignkeys to None
        player_pk_list = [p.pk for g in matrix for p in g]
        players_qs = self._PlayerClass().objects.filter(pk__in=player_pk_list)
        players_qs.update(group=None)

        self.group_set.all().delete()
        for i, row in enumerate(matrix, start=1):
            group = self._GroupClass().objects.create(
                subsession=self, id_in_subsession=i,
                session=self.session, round_number=self.round_number)
            group.set_players(row)

        if check_integrity:
            self.check_group_integrity()

    def set_groups(self, groups):
        self._set_groups(groups, check_integrity=True)

    @property
    def _Constants(self):
        return get_models_module(self._meta.app_config.name).Constants

    def _GroupClass(self):
        return models.get_model(self._meta.app_config.label, 'Group')

    def _PlayerClass(self):
        return models.get_model(self._meta.app_config.label, 'Player')

    def _first_round_group_matrix(self):
        players = list(self.get_players())

        groups = []
        first_player_index = 0

        for group_size in self._get_players_per_group_list():
            groups.append(
                players[first_player_index:first_player_index + group_size]
            )
            first_player_index += group_size
        return groups

    def _create_groups(self):
        if self.round_number == 1:
            group_matrix = self._first_round_group_matrix()
            self.set_groups(group_matrix)
        else:
            self.group_like_round(1)

    def group_like_round(self, round_number):
        previous_round = self.in_round(round_number)
        group_matrix = [
            self._PlayerClass().objects.filter(
                participant__in=[p.participant
                                 for p in group.player_set.all()],
                round_number=self.round_number).order_by('id_in_group')
            for group in previous_round.group_set.order_by('id_in_subsession')
                         .prefetch_related('player_set__participant')]

        # save to DB
        self.set_groups(group_matrix)

    def before_session_starts(self):
        '''This gets called at the beginning of every subsession, before the
        first page is loaded.

        3rd party programmer can put any code here, e.g. to loop through
        players and assign treatment parameters.

        '''
        pass

    def match_players(self, match_name):
        if self.round_number > 1:
            match_function = match_players.MATCHS[match_name]
            pxg = match_function(self)
            for group, players in zip(self.get_groups(), pxg):
                group.set_players(players)
