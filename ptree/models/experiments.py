import random

from django.contrib.contenttypes import generic
from django.contrib.contenttypes.models import ContentType

from ptree.db import models
from ptree.fields import RandomCharField
import ptree.constants as constants
from ptree.sessionlib.models import Session
from ptree.common import id_label_name
import ptree.user.models


class BaseExperiment(models.Model):
    """
    Base class for all Experiments.
    """

    label = models.CharField(max_length = 500,
                            null = True,
                            blank = True,
                            )

    session = models.ForeignKey(Session,
                                                related_name = '%(app_label)s_%(class)s',
                                                null=True)

    code = RandomCharField(length=8)

    experimenter = models.OneToOneField(
        ptree.user.models.Experimenter,
        related_name = '%(app_label)s_experiment',
        null=True)

    next_experiment_content_type = models.ForeignKey(ContentType,
                                                     null=True,
                                                     related_name = '%(app_label)s_%(class)s_as_next_experiment')
    next_experiment_object_id = models.PositiveIntegerField(null=True)
    next_experiment = generic.GenericForeignKey('next_experiment_content_type',
                                            'next_experiment_object_id',)

    previous_experiment_content_type = models.ForeignKey(ContentType,
                                                     null=True,
                                                     related_name = '%(app_label)s_%(class)s_as_previous_experiment')
    previous_experiment_object_id = models.PositiveIntegerField(null=True)
    previous_experiment = generic.GenericForeignKey('previous_experiment_content_type',
                                            'previous_experiment_object_id',)

    index_in_sequence_of_experiments = models.PositiveIntegerField(null=True)

    def is_last_experiment(self):
        return not self.next_experiment

    def name(self):
        return id_label_name(self.pk, self.label)

    def __unicode__(self):
        return self.name()

    def start_url(self):
        """The URL that a user is redirected to in order to start a treatment"""
        return '/{}/Initialize/?{}={}'.format(self.name_in_url,
                                              constants.user_code,
                                              self.code)


    def pick_treatment_with_open_match(self):
        return [m for m in self.matches() if m.is_ready_for_next_participant()][0].treatment

    def pick_treatment_for_incoming_participant(self):
        try:
            return self.pick_treatment_with_open_match()
        except IndexError:
            treatments = list(self.treatments())
            random.shuffle(treatments)
            return min(treatments, key=lambda treatment: len(treatment.participants()))

    def assign_participants_to_treatments(self):
        participants = list(self.participants())
        random.shuffle(participants)
        for participant in participants:
            participant.treatment = self.pick_treatment_for_incoming_participant()
            participant.add_to_existing_or_new_match()
            participant.save()

    def treatments(self):
        return self.treatment_set.all()

    def matches(self):
        return self.match_set.all()

    def participants(self):
        return self.participant_set.all()



    def experimenter_sequence_of_views(self):
        return []

    def experimenter_sequence_as_urls(self):
        """Converts the sequence to URLs.

        e.g.:
        sequence() returns something like [views.IntroPage, ...]
        sequence_as_urls() returns something like ['mygame/IntroPage', ...]
        """
        return [View.url(index) for index, View in enumerate(self.experimenter_sequence_of_views())]

    class Meta:
        abstract = True
        ordering = ['pk']