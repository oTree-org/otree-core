from django.contrib.contenttypes import generic
from django.contrib.contenttypes.models import ContentType

from ptree.fields import RandomCharField
from ptree.db import models
import ptree.sessionlib.models
import ptree.constants as constants
from ptree.common import add_params_to_url

class User(models.Model):
    """represents experimenter or participants"""
    # the participant's unique ID (and redemption code) that gets passed in the URL.
    code = RandomCharField(length = 8)

    visited = models.BooleanField(default=False)

    def start_url(self):
        raise NotImplementedError()

    def pages_as_urls(self):
        raise NotImplementedError()

    session = models.ForeignKey(
        ptree.sessionlib.models.Session,
        related_name = '%(app_label)s_%(class)s')

    index_in_pages = models.PositiveIntegerField(default=0)

    # 2/12/2014: i think the previous pointer is unnecessary because i can traverse via the reverse relation of the "next" pointer
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


    def progress(self):
        if not self.visited:
            return None
        return '{}/{} pages'.format(self.index_in_pages + 1,
                                    len(self.treatment.pages()))

    class Meta:
        abstract = True

class Experimenter(User):

    session_experimenter = models.ForeignKey(
        ptree.sessionlib.models.SessionExperimenter,
        null=True,
        related_name='experimenter'
    )

    experiment_content_type = models.ForeignKey(ContentType,
                                                null=True,
                                                related_name = 'experimenter')
    experiment_object_id = models.PositiveIntegerField(null=True)
    experiment = generic.GenericForeignKey('experiment_content_type',
                                           'experiment_object_id',
                                           )

    @property
    def session_user(self):
        return self.session_experimenter

    def start_url(self):
        return add_params_to_url(
            '/InitializeExperimenter/',
            {
                constants.experiment_code: self.experiment.code,
                constants.user_code: self.code,
            }
        )

    def pages_as_urls(self):
        return self.experiment.experimenter_pages_as_urls()
