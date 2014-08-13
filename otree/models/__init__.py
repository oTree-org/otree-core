from django.contrib.contenttypes import generic
from otree.sessionlib.models import Session, Participant
from otree.db import models
from importlib import import_module
from otree.common import _players, _matches

subsessions = import_module('otree.models.subsessions')
treatments = import_module('otree.models.treatments')
matches = import_module('otree.models.matches')
players = import_module('otree.models.players')



class BaseSubsession(subsessions.BaseSubsession):

    session = models.ForeignKey(
        Session,
        related_name = '%(app_label)s_%(class)s',
        null=True
    )


    name_in_url = None

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

    @property
    def treatments(self):
        if hasattr(self, '_treatments'):
            return self._treatments
        self._treatments = list(self.treatment_set.all())
        return self._treatments

    @property
    def matches(self):
        return _matches(self)

    @property
    def players(self):
        return _players(self)

    @property
    def app_name(self):
        return self._meta.app_label

    def pick_treatments(self, previous_round_treatments):
        return super(BaseSubsession, self).pick_treatments(previous_round_treatments)

    def pick_match_groups(self, previous_round_match_groups):
        return super(BaseSubsession, self).pick_match_groups(previous_round_match_groups)


    class Meta:
        abstract = True
        ordering = ['pk']

class BaseTreatment(treatments.BaseTreatment):

    @property
    def matches(self):
        return _matches(self)

    @property
    def players(self):
        return _players(self)

    label = models.CharField(max_length = 300, null = True, blank = True)

    session = models.ForeignKey(
        Session,
        null=True,
        related_name = '%(app_label)s_%(class)s'
    )

    class Meta:
        abstract = True
        ordering = ['pk']

class BaseMatch(matches.BaseMatch):

    players_per_match = 1

    session = models.ForeignKey(
        Session,
        related_name = '%(app_label)s_%(class)s'
    )

    @property
    def players(self):
        return _players(self)

    @players.setter
    def players(self, value):
        raise NotImplementedError()

    def get_player_by_role(self, role):
        return super(BaseMatch, self).get_player_by_role(role)

    def get_player_by_index(self, index):
        return super(BaseMatch, self).get_player_by_index(index)

    class Meta:
        abstract = True
        verbose_name_plural = "matches"
        ordering = ['pk']

class BasePlayer(players.BasePlayer):
    # starts from 1, not 0.
    index_among_players_in_match = models.PositiveIntegerField(
        null = True,
        doc="Index starting from 1. In multiplayer games, indicates whether this is player 1, player 2, etc."
    )

    payoff = models.MoneyField(
        null=True,
        doc="""The payoff the player made in this subsession, in cents"""
    )

    participant = models.ForeignKey(
        Participant,
        related_name = '%(app_label)s_%(class)s'
    )


    def other_players_in_match(self):
        return [p for p in self.match.players if p != self]

    def other_players_in_subsession(self):
        return [p for p in self.subsession.players if p != self]


    class Meta:
        abstract = True
        ordering = ['pk']