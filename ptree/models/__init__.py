from django.contrib.contenttypes import generic
from ptree.sessionlib.models import Session, SessionParticipant
from ptree.db import models
from importlib import import_module

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

    participants_per_match = 1
    name_in_url = None

    next_subsession = generic.GenericForeignKey('_next_subsession_content_type',
                                            '_next_subsession_object_id',)

    previous_subsession = generic.GenericForeignKey('_previous_subsession_content_type',
                                            '_previous_subsession_object_id',)


    def treatments(self):
        return list(self.treatment_set.all())

    def matches(self):
        return list(self.match_set.all())

    def participants(self):
        return list(self.participant_set.all())

    @property
    def app_name(self):
        return self._meta.app_label

    class Meta:
        abstract = True
        ordering = ['pk']

class BaseTreatment(treatments.BaseTreatment):

    def matches(self):
        return list(self.match_set.all())

    def participants(self):
        return list(self.participant_set.all())

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
    session = models.ForeignKey(
        Session,
        related_name = '%(app_label)s_%(class)s'
    )

    def participants(self):
        return list(self.participant_set.all())

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

    bonus = models.PositiveIntegerField(
        null=True,
        doc="""The bonus the participant made in this subsession, in cents"""
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

    class Meta:
        abstract = True
        ordering = ['pk']