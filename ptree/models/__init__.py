from ptree.db import models
from django.contrib.contenttypes import generic
from ptree.sessionlib.models import Session, SessionParticipant

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

    def experimenter_pages(self):
        return []

    @property
    def app_label(self):
        return self._meta.app_label

    class Meta:
        abstract = True

class BaseTreatment(treatments.BaseTreatment):

    def pages(self):
        raise NotImplementedError()

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

    participants_per_match = models.PositiveIntegerField(default=1)

    class Meta:
        abstract = True

class BaseMatch(matches.BaseMatch):
    session = models.ForeignKey(
        Session,
        related_name = '%(app_label)s_%(class)s'
    )

    def participants(self):
        return list(self.participant_set.all())

    # starts from 1, not 0.
    index_among_participants_in_match = models.PositiveIntegerField(null = True)

    bonus = models.PositiveIntegerField(null=True)

    session_participant = models.ForeignKey(
        SessionParticipant,
        related_name = '%(app_label)s_%(class)s'
    )
