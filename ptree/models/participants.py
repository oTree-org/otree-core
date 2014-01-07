from django.db import models
from ptree.fields import RandomCharField
import ptree.constants as constants
from django.conf import settings
from ptree.common import currency
import ptree.sequence_of_experiments.models
from ptree.common import add_params_to_url
from django.contrib.contenttypes import generic
from django.contrib.contenttypes.models import ContentType

class BaseParticipant(models.Model):
    """
    Base class for all participants.
    """

    # the participant's unique ID (and redemption code) that gets passed in the URL.
    code = RandomCharField(length = 8)

    visited = models.BooleanField(default=False)

    participant_in_sequence_of_experiments = models.ForeignKey(ptree.sequence_of_experiments.models.Participant,
                                                               related_name = '%(app_label)s_%(class)s')

    index_among_participants_in_match = models.PositiveIntegerField(null = True)

    index_in_sequence_of_views = models.PositiveIntegerField(default=0)

    me_in_previous_experiment_content_type = models.ForeignKey(ContentType,
                                                      null=True,
                                                      related_name = '%(app_label)s_%(class)s_previous')
    me_in_previous_experiment_object_id = models.PositiveIntegerField(null=True)
    me_in_previous_experiment = generic.GenericForeignKey('me_in_previous_experiment_content_type',
                                                'me_in_previous_experiment_object_id',)

    me_in_next_experiment_content_type = models.ForeignKey(ContentType,
                                                      null=True,
                                                      related_name = '%(app_label)s_%(class)s_next')
    me_in_next_experiment_object_id = models.PositiveIntegerField(null=True)
    me_in_next_experiment = generic.GenericForeignKey('me_in_next_experiment_content_type',
                                                'me_in_next_experiment_object_id',)


    def name(self):
        return self.participant_in_sequence_of_experiments.__unicode__()

    def __unicode__(self):
        return self.name()

    def start_url(self):
        return add_params_to_url(self.experiment.start_url(), {constants.participant_code: self.code})

    def bonus(self):
        """
        The bonus the participant gets paid, in addition to their base pay.

        Should return None if the bonus cannot yet be determined.
        """
        raise NotImplementedError()

    def bonus_display(self):
        """printable version of the bonus"""
        try:
            return currency(self.bonus())
        except:
            return currency(None)

    bonus_display.short_description = 'Bonus'

    class Meta:
        abstract = True
        ordering = ['pk']