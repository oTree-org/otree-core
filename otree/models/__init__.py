from django.contrib.contenttypes import generic
from otree.sessionlib.models import Session, Participant
from otree.db import models
from otree.common import _players, _groups
from otree.models import subsessions, groups, players


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

    number_of_rounds = models.PositiveIntegerField(
        doc='Number of rounds for which this subsession is played'
    )

    def get_groups(self):
        return _groups(self)

    def get_players(self):
        return _players(self)

    @property
    def app_name(self):
        return self._meta.app_label

    def next_round_groups(self, previous_round_groups):
        return super(BaseSubsession, self).next_round_groups(previous_round_groups)

    def previous_rounds(self):
        return super(BaseSubsession, self).previous_rounds()

    class Meta:
        abstract = True
        ordering = ['pk']

class BaseGroup(groups.BaseGroup):

    players_per_group = 1

    session = models.ForeignKey(
        Session,
        related_name = '%(app_label)s_%(class)s'
    )

    def get_players(self):
        return _players(self)

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

    payoff = models.MoneyField(
        null=True,
        doc="""The payoff the player made in this subsession, in cents"""
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