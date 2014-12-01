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

    _next_subsession_content_type = models.ForeignKey(ContentType,
                                                     null=True,
                                                     related_name = '%(app_label)s_%(class)s_as_next_subsession')
    _next_subsession_object_id = models.PositiveIntegerField(null=True)

    _previous_subsession_content_type = models.ForeignKey(ContentType,
                                                     null=True,
                                                     related_name = '%(app_label)s_%(class)s_as_previous_subsession')

    _previous_subsession_object_id = models.PositiveIntegerField(null=True)


    #FIXME: this should start at 1, to be consistent with id_in_group
    _index_in_subsessions = models.PositiveIntegerField(
        null=True,
        doc="starts from 0. indicates the position of this subsession among other subsessions in the session."
    )

    def previous_rounds(self):

        rounds = []
        current_round = self
        for i in range(self.round_number-1):
            current_round = current_round.previous_subsession
            rounds.append(current_round)
        # return starting with round 1
        rounds.reverse()
        return rounds

    def all_rounds(self):
        return self.previous_rounds() + [self]

    def name(self):
        return str(self.pk)

    def __unicode__(self):
        return self.name()


    def previous_round(self):
        '''finds non-contiguous rounds'''
        s = self
        while True:
            s = s.previous_subsession
            if not s:
                return None
            if s.app_name == self.app_name:
                return s

    def next_round_groups(self, current_round_group_matrix):
        return current_round_group_matrix

    def _players_per_group(self):
        ppg = self._Constants.players_per_group
        if isinstance(ppg, (int, long)) and ppg > 1:
            return ppg
        # otherwise, the group is the whole subsession
        return len(self.session.get_participants())


    def _num_groups(self):
        """number of groups in this subsession"""
        return self.player_set.count()/self._players_per_group()

    def _next_open_group(self):
        """Get the next group that is accepting players.
        (or none if it does not exist)
        """
        for group in self.group_set.all():
            if len(group.player_set.all()) < self._players_per_group():
                return group

    def _random_group_matrix(self):
        players = list(self.player_set.all())
        random.shuffle(players)
        groups = []
        players_per_group = self._players_per_group()

        # divide into equal size groups
        for i in range(0, len(players), players_per_group):
            groups.append(players[i:i+players_per_group])
        return groups

    def _group_objects_to_matrix(self):
        """puts Group objects in matrix format so you can do matrix permutations"""
        return [list(g.get_players()) for g in self.group_set.all()]

    def _group_matrix_to_objects(self, group_matrix):
        """inverse operation of _group_objects_to_matrix"""
        for group_list in group_matrix:
            group = self._next_open_group()
            for player in group_list:
                player._assign_to_group(group)
            group.save()

    @property
    def _Constants(self):
        return get_models_module(self._meta.app_label).Constants

    def _GroupClass(self):
        return models.get_model(self._meta.app_label, 'Group')

    def _create_empty_groups(self):
        GroupClass = self._GroupClass()
        for i in range(self._num_groups()):
            m = GroupClass._create(self)

    def first_round_groups(self):
        return self._random_group_matrix()

    def _assign_groups(self):
        previous_round = self.previous_round()
        if not previous_round:
            current_round_group_matrix = self.first_round_groups()
        else:
            previous_round_group_matrix = previous_round._group_objects_to_matrix()
            current_round_group_matrix = previous_round.next_round_groups(previous_round_group_matrix)
            for i, group_list in enumerate(current_round_group_matrix):
                for j, player in enumerate(group_list):
                    # for every entry (i,j) in the matrix, follow the pointer to the same person in the next round
                    current_round_group_matrix[i][j] = player._me_in_next_subsession
        # save to DB
        self._group_matrix_to_objects(current_round_group_matrix)

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
        for p in self.get_players():
            p.save()
        for g in self.get_groups():
            g.save()


    def previous_subsession_is_in_same_app(self):
        previous_subsession = self.previous_subsession
        return previous_subsession and previous_subsession._meta.app_label == self._meta.app_label

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
