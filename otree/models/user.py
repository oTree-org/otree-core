from django.contrib.contenttypes import generic
from django.contrib.contenttypes.models import ContentType

from otree.session.models import Session, SessionExperimenter
from otree.db import models
import otree.constants as constants
from otree.common_internal import add_params_to_url, get_models_module
from save_the_change.mixins import SaveTheChange

class User(SaveTheChange, models.Model):
    """represents experimenter or players"""
    # the player's unique ID that gets passed in the URL.
    code = models.RandomCharField(length = 8)

    _index_in_game_pages = models.PositiveIntegerField(
        default=0,
        doc='Index in the list of pages returned by views_module.pages()'
    )

    session = models.ForeignKey(
        Session,
        related_name = '%(app_label)s_%(class)s')

    _in_previous_subsession_content_type = models.ForeignKey(ContentType,
                                                      null=True,
                                                      related_name = '%(app_label)s_%(class)s_previous')
    _in_previous_subsession_object_id = models.PositiveIntegerField(null=True)

    _in_next_subsession_content_type = models.ForeignKey(ContentType,
                                                      null=True,
                                                      related_name = '%(app_label)s_%(class)s_next')
    _in_next_subsession_object_id = models.PositiveIntegerField(null=True)

    _in_previous_subsession = generic.GenericForeignKey('_in_previous_subsession_content_type',
                                                '_in_previous_subsession_object_id',)

    _in_next_subsession = generic.GenericForeignKey('_in_next_subsession_content_type',
                                                '_in_next_subsession_object_id',)


    class Meta:
        abstract = True


class Experimenter(User):

    session_experimenter = models.ForeignKey(
        SessionExperimenter,
        null=True,
        related_name='experimenter'
    )

    subsession_content_type = models.ForeignKey(ContentType,
                                                null=True,
                                                related_name = 'experimenter')
    subsession_object_id = models.PositiveIntegerField(null=True)
    subsession = generic.GenericForeignKey('subsession_content_type',
                                           'subsession_object_id',
                                           )

    class Meta:
        app_label = 'otree'

    @property
    def _session_user(self):
        return self.session_experimenter

    def _pages_as_urls(self):
        return self.subsession._experimenter_pages_as_urls()
