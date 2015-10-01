#!/usr/bin/env python
# -*- coding: utf-8 -*-

from otree_save_the_change.mixins import SaveTheChange
from otree.db import models
from otree.common_internal import (
    get_models_module, get_players, get_groups, flatten)
from otree.models_concrete import GroupSize
from otree import match_players


class BaseSubsession(SaveTheChange, models.Model):
    """Base class for all Subsessions.

    """

    class Meta:
        abstract = True

    code = models.RandomCharField(length=8)

    # FIXME: this should start at 1, to be consistent with id_in_group
    _index_in_subsessions = models.PositiveIntegerField(
        null=True, doc=(
            "starts from 0. indicates the position of this subsession "
            "among other subsessions in the session."
        )
    )

    def in_previous_rounds(self):
        qs = type(self).objects.filter(
            session=self.session,
            round_number__lt=self.round_number
        ).order_by('round_number')

        return list(qs)

    def in_all_rounds(self):
        return self.in_previous_rounds() + [self]

    def name(self):
        return str(self.pk)

    def __unicode__(self):
        return self.name()

    _groups = []
    _players = []

    def _in_previous_round(self):
        return type(self).objects.filter(
            session=self.session,
            round_number=self.round_number - 1
        ).get()

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
        subsession_size = len(self.get_players())
        if ppg is None:
            return [subsession_size]

        # if groups have variable sizes, you can put it in a list
        if isinstance(ppg, (list, tuple)):
            assert all(n > 1 for n in ppg)
            group_cycle = ppg
        else:
            assert isinstance(ppg, (int, long)) and ppg > 1
            group_cycle = [ppg]

        num_group_cycles = subsession_size / sum(group_cycle)
        return group_cycle * num_group_cycles

    def get_groups(self):
        return get_groups(self, refresh_from_db=False)

    def _get_players(self, refresh_from_db=False):
        return get_players(
            self, order_by='pk',
            refresh_from_db=refresh_from_db
        )

    def get_players(self):
        return self._get_players()

    def check_group_integrity(self):
        '''

        2015-4-17: can't check this from set_players,
        because sometimes we are intentionally in an inconsistent state
        e.g., if group_by_arrival_time is true, and some players have not
        been assigned to groups yet
        '''
        players = get_players(self, order_by='id', refresh_from_db=True)
        groups = [get_players(g, 'id', True) for g in get_groups(self, True)]
        players_from_groups = flatten(groups)

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
                matrix.append(group.player_set.all())
            else:
                players_list = group
                matrix.append(players_list)
                # assume it's an iterable containing the players
        # Before deleting groups, Need to set the foreignkeys to None
        for g in matrix:
            for p in g:
                p.group = None
                p.save()
        self.group_set.all().delete()
        for i, row in enumerate(matrix, start=1):
            group = self._create_group()
            group.set_players(row)
            group.id_in_subsession = i

        if check_integrity:
            self.check_group_integrity()

    def set_groups(self, groups):
        self._set_groups(groups, check_integrity=True)

    @property
    def _Constants(self):
        return get_models_module(self._meta.app_config.name).Constants

    def _GroupClass(self):
        return models.get_model(self._meta.app_config.label, 'Group')

    def _create_group(self):
        '''should not be public API, because could leave the players in an
        inconsistent state,

        where id_in_group is not updated. the only call should be to
        subsession.create_groups()

        '''
        GroupClass = self._GroupClass()
        group = GroupClass(subsession=self, session=self.session)

        # need to save it before you assign the player.group ForeignKey
        group.save()
        return group

    def _first_round_group_matrix(self):
        players = list(self.player_set.all())

        groups = []
        first_player_index = 0

        for group_size in self._get_players_per_group_list():
            groups.append(
                players[first_player_index:first_player_index + group_size]
            )
            first_player_index += group_size
        return groups

    def _set_players_per_group_list(self):
        for index, group_size in enumerate(self._get_players_per_group_list()):
            GroupSize(
                app_label=self._meta.app_config.name,
                subsession_pk=self.pk,
                group_index=index,
                group_size=group_size,
            ).save()

    def _create_empty_groups(self):
        num_groups = len(self._get_players_per_group_list())
        self._set_groups(
            [[] for i in range(num_groups)],
            check_integrity=False
        )
        groups = self.get_groups()
        for group in groups:
            group._is_missing_players = True
            group.save()

    def _create_groups(self):
        if self.round_number == 1:
            group_matrix = self._first_round_group_matrix()
        else:
            previous_round = self._in_previous_round()
            group_matrix = [
                group._get_players(refresh_from_db=True)
                for group in get_groups(previous_round, refresh_from_db=True)
            ]
            for i, group_list in enumerate(group_matrix):
                for j, player in enumerate(group_list):

                    # for every entry (i,j) in the matrix, follow the pointer
                    # to the same person in the next round
                    group_matrix[i][j] = player._in_next_round()

        # save to DB
        self.set_groups(group_matrix)

    def _get_open_group(self):
        # force refresh from DB so that next call to this function does not
        # show the group as still missing players
        groups_missing_players = self.group_set.filter(
            _is_missing_players=True
        )
        for group in groups_missing_players:
            if len(group.get_players()) > 0:
                return group
        return groups_missing_players[0]

    def before_session_starts(self):
        '''This gets called at the beginning of every subsession, before the
        first page is loaded.

        3rd party programmer can put any code here, e.g. to loop through
        players and assign treatment parameters.

        '''
        pass

    def _initialize(self):
        '''wrapper method for self.before_session_starts()'''
        self.before_session_starts()
        # needs to be get_players and get_groups instead of
        # self.player_set.all() because that would just send a new query
        # to the DB
        for p in self.get_players():
            p.save()
        for g in self.get_groups():
            g.save()

        # subsession.save() gets called in the parent method

    def match_players(self, match_name):
        if self.round_number > 1:
            match_function = match_players.MATCHS[match_name]
            pxg = match_function(self)
            for group, players in zip(self.get_groups(), pxg):
                group.set_players(players)
