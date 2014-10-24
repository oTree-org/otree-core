import random

from django.contrib.contenttypes import generic
from django.contrib.contenttypes.models import ContentType

from otree.db import models

from otree.fields import RandomCharField
import otree.constants as constants
import math
from otree.common import flatten, _views_module
import itertools
from django_extensions.db.fields.json import JSONField

class BaseSubsession(models.Model):
    """
    Base class for all Subsessions.
    """

    code = RandomCharField(length=8)

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

    _skip = models.BooleanField(
        default=False,
        doc="""whether the experimenter made the players skip this subsession"""
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

    def _start_url(self):
        """The URL that a user is redirected to in order to start a treatment.
        3/2/2014: is this still used for anything? i think i am moving towards deprecating it.
        """
        return '/{}/Initialize/?{}={}'.format(self.name_in_url,
                                              constants.user_code,
                                              self.code)

    def previous_round(self):
        '''finds non-contiguous rounds'''
        s = self
        while True:
            s = s.previous_subsession
            if not s:
                return None
            if s.app_name == self.app_name:
                return s

    def next_round_groups(self, previous_round_groups):
        return previous_round_groups

    def _num_groups(self):
        """number of groups in this subsession"""
        return self.player_set.count()/self._GroupClass().players_per_group

    def _next_open_group(self):
        """Get the next group that is accepting players.
        (or none if it does not exist)
        """
        try:
            return (m for m in self.group_set.all() if m._is_ready_for_next_player()).next()
        except StopIteration:
            return None

    def _random_group_lists(self):
        players = list(self.player_set.all())
        random.shuffle(players)
        groups = []
        players_per_group = self._GroupClass().players_per_group
        for i in range(0, len(players), players_per_group):
            groups.append(players[i:i+players_per_group])
        return groups

    def _group_objects_to_lists(self):
        return [list(m.player_set.order_by('id_in_group').all()) for m in self.group_set.all()]

    def _group_lists_to_objects(self, group_lists):
        for group_list in group_lists:
            group = self._next_open_group()
            for player in group_list:
                player._assign_to_group(group)
            group.save()

    def _GroupClass(self):
        return models.get_model(self._meta.app_label, 'Group')

    def _create_empty_groups(self):
        GroupClass = self._GroupClass()
        for i in range(len(self.get_players())/GroupClass.players_per_group):
            m = GroupClass._create(self)

    def first_round_groups(self):
        return self._random_group_lists()

    def _assign_groups(self):
        previous_round = self.previous_round()
        if not previous_round:
            group_lists = self.first_round_groups()
        else:
            previous_round_group_lists = previous_round._group_objects_to_lists()
            group_lists = self.next_round_groups(previous_round_group_lists)
            for i, group_list in enumerate(group_lists):
                for j, player in enumerate(group_list):
                    group_lists[i][j] = player._me_in_next_subsession
        self._group_lists_to_objects(group_lists)

    def _initialize(self):
        self.initialize()
        for p in self.get_players():
            p.save()
        for g in self.get_groups():
            g.save()

    def initialize(self):
        '''
        This gets called at the beginning of every subsession, before the first page is loaded.
        3rd party programmer can put any code here, e.g. to loop through players and
        assign treatment parameters.
        '''
        pass

    def previous_subsession_is_in_same_app(self):
        previous_subsession = self.previous_subsession
        return previous_subsession and previous_subsession._meta.app_label == self._meta.app_label

    def _experimenter_pages(self):
        views_module = _views_module(self)
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