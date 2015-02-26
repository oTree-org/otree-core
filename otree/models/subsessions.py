#!/usr/bin/env python
# -*- coding: utf-8 -*-

import random

from otree.db import models
from otree.common_internal import get_views_module
from otree.common_internal import (
    get_models_module, get_players, get_groups,
)
from otree.models_concrete import GroupSize


class BaseSubsession(models.Model):
    """Base class for all Subsessions.

    """

    class Meta:
        abstract = True

    code = models.RandomCharField(length=8)

    _experimenter = models.OneToOneField(
        'otree.Experimenter', null=True,
        related_name='%(app_label)s_subsession'
    )

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
    _player = None

    def in_previous_round(self):
        return type(self).objects.filter(
            session=self.session,
            round_number=self.round_number - 1
        ).get()

    def _get_players_per_group_list(self):
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

    def _min_players_multiple(self):
        self._Constants.players_per_group

    def set_groups(self, groups):
        """elements in the list can be sublists, or group objects.

        Maybe this should be re-run after before_session_starts() to ensure that
        id_in_groups are consistent. Or at least we should validate.


        warning: this deletes the groups and any data stored on them
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
        for row in matrix:
            group = self._create_group()
            group.set_players(row)

    @property
    def _Constants(self):
        return get_models_module(self._meta.app_config.name).Constants

    def _GroupClass(self):
        return models.get_model(self._meta.app_label, 'Group')

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

    def _random_group_matrix(self):
        players = list(self.player_set.all())

        random.shuffle(players)

        groups = []
        first_player_index = 0

        # if players_per_group is an integer, then outer_loops == num_groups
        # this is to enable apps with variable group sizes

        for group_size in self._get_players_per_group_list():
            groups.append(
                players[first_player_index:first_player_index + group_size]
            )
            first_player_index += group_size
        return groups

    def _set_players_per_group_list(self):
        for index, group_size in enumerate(self._get_players_per_group_list()):
            GroupSize(
                app_label=self._meta.app_label,
                subsession_pk=self.pk,
                group_index=index,
                group_size=group_size,
            ).save()

    def _create_empty_groups(self):
        num_groups = len(self._get_players_per_group_list())
        self.set_groups([[] for i in range(num_groups)])
        groups = self.get_groups()
        for group in groups:
            group._is_missing_players = True
            group.save()

    def _create_groups(self):
        if self.round_number == 1:
            group_matrix = self._random_group_matrix()
        else:
            previous_round = self.in_previous_round()
            group_matrix = [
                get_players(group, refresh_from_db=True)
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

    def _experimenter_pages(self):
        views_module = get_views_module(self._meta.app_label)
        if hasattr(views_module, 'experimenter_pages'):
            return views_module.experimenter_pages() or []
        return []

    def _experimenter_pages_as_urls(self):
        """Converts the sequence to URLs.

        e.g.:
        """
        return [
            View.url(self._experimenter.session_experimenter, index)
            for index, View in enumerate(self._experimenter_pages())
        ]
