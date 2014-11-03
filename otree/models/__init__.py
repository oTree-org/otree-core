
from importlib import import_module
from django.contrib.contenttypes import generic
from otree.session.models import Session, Participant
from otree.db import models
from otree.common import _players, _groups

# NOTE: this imports the following submodules and then subclasses several classes
# importing is done via import_module rather than an ordinary import.
# The only reason for this is to hide the base classes from IDEs like PyCharm,
# so that those members/attributes don't show up in autocomplete,
# including all the built-in django model fields that an ordinary oTree programmer will never need or want.
# if this was a conventional Django project I wouldn't do it this way,
# but because oTree is aimed at newcomers who may need more assistance from their IDE,
# I want to try this approach out.
# this module is also a form of documentation of the public API.

subsessions = import_module('otree.models.subsessions')
groups = import_module('otree.models.groups')
players = import_module('otree.models.players')
user = import_module('otree.models.user')

class BaseSubsession(subsessions.BaseSubsession):

    session = models.ForeignKey(
        Session,
        related_name = '%(app_label)s_%(class)s',
        null=True
    )

    next_subsession = generic.GenericForeignKey('_next_subsession_content_type',
                                            '_next_subsession_object_id',)

    previous_subsession = generic.GenericForeignKey('_previous_subsession_content_type',
                                            '_previous_subsession_object_id',)

    round_number = models.PositiveIntegerField(
        doc='''
        If this subsession is repeated (i.e. has multiple rounds), this field stores the position (index) of this subsession,
        among subsessions in the same app.
        For example, if a session consists of the subsessions:
        [app1, app2, app1, app1, app3]
        Then the round numbers of these subsessions would be:
        [1, 1, 2, 3, 1]
        '''
    )

    def get_groups(self, refresh_from_db=False):
        return _groups(self, refresh_from_db)

    def get_players(self, refresh_from_db=False):
        return _players(self, refresh_from_db)

    @property
    def app_name(self):
        return self._meta.app_label

    def first_round_groups(self):
        return super(BaseSubsession, self).first_round_groups()

    def next_round_groups(self, current_round_group_matrix):
        return super(BaseSubsession, self).next_round_groups(current_round_group_matrix)

    def previous_rounds(self):
        return super(BaseSubsession, self).previous_rounds()

    class Meta:
        abstract = True
        ordering = ['pk']

class BaseGroup(groups.BaseGroup):

    session = models.ForeignKey(
        Session,
        related_name = '%(app_label)s_%(class)s'
    )

    def get_players(self, refresh_from_db=False):
        return _players(self, refresh_from_db)

    def get_player_by_role(self, role):
        return super(BaseGroup, self).get_player_by_role(role)



    def get_player_by_id(self, index):
        return super(BaseGroup, self).get_player_by_id(index)

    class Meta:
        abstract = True
        ordering = ['pk']

class BasePlayer(players.BasePlayer):
    # starts from 1, not 0.
    id_in_group = models.PositiveIntegerField(
        null = True,
        doc="Index starting from 1. In multiplayer games, indicates whether this is player 1, player 2, etc."
    )

    payoff = models.CurrencyField(
        null=True,
        doc="""The payoff the player made in this subsession"""
    )

    participant = models.ForeignKey(
        Participant,
        related_name = '%(app_label)s_%(class)s'
    )


    def me_in_previous_rounds(self):
        return super(BasePlayer, self).me_in_previous_rounds()

    def me_in_all_rounds(self):
        return super(BasePlayer, self).me_in_all_rounds()

    def get_others_in_group(self):
        return [p for p in self.group.get_players() if p != self]

    def get_others_in_subsession(self):
        return [p for p in self.subsession.get_players() if p != self]

    def get_quiz_question(self, field_name):
        return super(BasePlayer, self).get_quiz_question(field_name)

    def role(self):
        return super(BasePlayer, self).role()

    class Meta:
        abstract = True
        ordering = ['pk']
