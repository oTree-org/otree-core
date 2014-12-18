import random

from django.contrib.contenttypes import generic
from django.contrib.contenttypes.models import ContentType

from otree.db import models

import otree.constants as constants
import math
from otree.common_internal import flatten, get_views_module
import itertools
from django_extensions.db.fields.json import JSONField
from otree.common_internal import get_models_module

class BaseSubsession(models.Model):
    """
    Base class for all Subsessions.
    """

    code = models.RandomCharField(length=8)

    _experimenter = models.OneToOneField(
        'otree.Experimenter',
        related_name = '%(app_label)s_subsession',
        null=True)

    #FIXME: this should start at 1, to be consistent with id_in_group
    _index_in_subsessions = models.PositiveIntegerField(
        null=True,
        doc="starts from 0. indicates the position of this subsession among other subsessions in the session."
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

    def in_previous_round(self):
        return type(self).objects.filter(
            session=self.session,
            round_number=self.round_number-1
        ).get()


    def _players_per_group(self):
        ppg = self._Constants.players_per_group
        if isinstance(ppg, (int, long)) and ppg > 1:
            return ppg
        # otherwise, the group is the whole subsession
        return len(self.session.get_participants())

    def _random_group_matrix(self):
        players = list(self.player_set.all())
        players_per_group = self._players_per_group()

        groups = []
        random.shuffle(players)

        # divide into equal size groups
        for i in range(0, len(players), players_per_group):
            groups.append(players[i:i+players_per_group])
        return groups


    def set_groups(self, groups):
        """elements in the list can be sublists, or group objects.
        maybe this should be re-run after initialize() to ensure that id_in_groups are consistent.
        or at least we should validate.
        """
        self.group_set.all().delete()
        # first, get players in each group
        matrix = []
        for group in groups:
            if isinstance(group, self._GroupClass()):
                matrix.append(group.player_set.all())
            else:
                players_list = group
                matrix.append(players_list)
                # assume it's an iterable containing the players
        for row in matrix:
            group = self._create_group()
            group.set_players(row)


    @property
    def _Constants(self):
        return get_models_module(self._meta.app_config.name).Constants

    def _GroupClass(self):
        return models.get_model(self._meta.app_label, 'Group')

    def _create_group(self):
        '''should not be public API, because could leave the players in an inconsistent state,
        where id_in_group is not updated. the only call should be to subsession.create_groups()
        '''
        GroupClass = self._GroupClass()
        group = GroupClass(
            subsession = self,
            session = self.session
        )
        # need to save it before you assign the player.group ForeignKey
        group.save()
        return group

    def first_round_groups(self):
        return self._random_group_matrix()

    def _create_groups(self):
        if self.round_number == 1:
            group_matrix = self.first_round_groups()
        else:
            previous_round = self.in_previous_round()
            group_matrix = [list(g.player_set.all()) for g in previous_round.group_set.all()]
            for i, group_list in enumerate(group_matrix):
                for j, player in enumerate(group_list):
                    # for every entry (i,j) in the matrix, follow the pointer to the same person in the next round
                    group_matrix[i][j] = player._in_next_round()
        # save to DB
        self.set_groups(group_matrix)

    def initialize(self):
        '''
        This gets called at the beginning of every subsession, before the first page is loaded.
        3rd party programmer can put any code here, e.g. to loop through players and
        assign treatment parameters.
        '''
        pass

    def _initialize(self):
        '''wrapper method for self.initialize()'''
        self.initialize()
        for p in self.player_set.all():
            p.save()
        for g in self.group_set.all():
            g.save()


    def _experimenter_pages(self):
        views_module = get_views_module(self._meta.app_label)
        if hasattr(views_module, 'experimenter_pages'):
            return views_module.experimenter_pages() or []
        return []

    def _experimenter_pages_as_urls(self):
        """Converts the sequence to URLs.

        e.g.:
        pages() returns something like [views.IntroPage, ...]
        pages_as_urls() returns something like ['mygame/IntroPage', ...]
        """
        return [View.url(self._experimenter.session_experimenter, index) for index, View in enumerate(self._experimenter_pages())]


    class Meta:
        abstract = True
