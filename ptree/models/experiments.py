from django.db import models
from ptree.fields import RandomCharField
import ptree.constants as constants
from django.template import defaultfilters
import random
from django.conf import settings
from django.contrib.contenttypes import generic
from django.contrib.contenttypes.models import ContentType
from ptree.sequence_of_experiments.models import SequenceOfExperiments

class BaseExperiment(models.Model):
    """
    Base class for all Experiments.
    """

    name = models.CharField(max_length = 500, null = True, blank = True)
    code = RandomCharField(length=8)
    experimenter_access_code = RandomCharField(length=8)
    sequence_of_experiments_access_code = RandomCharField(length=8)

    sequence_of_experiments = models.ForeignKey(SequenceOfExperiments,
                                                null=True,
                                                related_name = '%(app_label)s_%(class)s')

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

    def is_last_experiment(self):
        return not self.next_experiment

    def unicode(self):
        """Define this because Django-Inspect-Model (django-inspect-model.rtfd.org/en/latest/#usage)
        doesn't recognize the __unicode__ method, and Django-data-exports relies on this."""
        return self.name or str(self.pk)

    unicode.short_description = 'name'

    def __unicode__(self):
        return self.unicode()

    def experimenter_input_url(self):
        return '/{}/ExperimenterLaunch/?{}={}&{}={}'.format(self.url_base,
                                                          constants.experiment_code,
                                                          self.code,
                                                          constants.experimenter_access_code,
                                                          self.experimenter_access_code
                                                          )

    def start_url(self, in_sequence_of_experiments = False):
        """The URL that a user is redirected to in order to start a treatment"""
        url = '/{}/GetTreatmentOrParticipant/?{}={}'.format(self.url_base,
                                                             constants.experiment_code_obfuscated,
                                                             self.code)
        if in_sequence_of_experiments:
            url += '&{}={}'.format(constants.sequence_of_experiments_access_code,
                                   self.sequence_of_experiments_access_code)
        return url


    def pick_treatment_for_incoming_participant(self):
        return random.choice(self.treatments())

    def treatments(self):
        return self.treatment_set.all()

    def matches(self):
        return self.match_set.all()

    def participants(self):
        return self.participant_set.all()

    def experimenter_sequence_of_views(self):
        raise NotImplementedError()

    def experimenter_sequence_as_urls(self):
        """Converts the sequence to URLs.

        e.g.:
        sequence() returns something like [views.IntroPage, ...]
        sequence_as_urls() returns something like ['mygame/IntroPage', ...]
        """
        return [View.url() for index, View in enumerate(self.experimenter_sequence_of_views())]

    class Meta:
        abstract = True
        ordering = ['pk']