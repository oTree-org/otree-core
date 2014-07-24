from django.contrib.contenttypes import generic
from ptree.sessionlib.models import Session, SessionParticipant
from ptree.db import models
from importlib import import_module
from ptree.common import _participants, _matches

subsessions = import_module('ptree.models.subsessions')
treatments = import_module('ptree.models.treatments')
matches = import_module('ptree.models.matches')
participants = import_module('ptree.models.participants')



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
    def participants(self):
        return _participants(self)

    @property
    def app_name(self):
        return self._meta.app_label

    class Meta:
        abstract = True
        ordering = ['pk']

class BaseTreatment(treatments.BaseTreatment):

    @property
    def matches(self):
        return _matches(self)

    @property
    def participants(self):
        return _participants(self)

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

    participants_per_match = 1

    session = models.ForeignKey(
        Session,
        related_name = '%(app_label)s_%(class)s'
    )

    @property
    def participants(self):
        return _participants(self)

    class Meta:
        abstract = True
        verbose_name_plural = "matches"
        ordering = ['pk']

class BaseParticipant(participants.BaseParticipant):
    # starts from 1, not 0.
    index_among_participants_in_match = models.PositiveIntegerField(
        null = True,
        doc="Index starting from 1. In multiplayer games, indicates whether this is participant 1, participant 2, etc."
    )

    payoff = models.PositiveIntegerField(
        null=True,
        doc="""The payoff the participant made in this subsession, in cents"""
    )

    session_participant = models.ForeignKey(
        SessionParticipant,
        related_name = '%(app_label)s_%(class)s'
    )

    # me_in_previous_subsession and me_in_next_subsession are duplicated between this model and experimenter model,
    # to make autocomplete work
    me_in_previous_subsession = generic.GenericForeignKey('me_in_previous_subsession_content_type',
                                                'me_in_previous_subsession_object_id',)

    me_in_next_subsession = generic.GenericForeignKey('me_in_next_subsession_content_type',
                                                'me_in_next_subsession_object_id',)

    def other_participants_in_match(self):
        return [p for p in self.match.participants() if p != self]

    def other_participants_in_subsession(self):
        return [p for p in self.subsession.participants() if p != self]


    class Meta:
        abstract = True
        ordering = ['pk']