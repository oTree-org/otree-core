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

    visited = models.BooleanField(default=False,
          doc="""Whether this user's start URL was opened"""
                                  )



    def _pages_as_urls(self):
        raise NotImplementedError()

    session = models.ForeignKey(
        Session,
        related_name = '%(app_label)s_%(class)s')


    index_in_pages = models.PositiveIntegerField(default=0)

    _me_in_previous_subsession_content_type = models.ForeignKey(ContentType,
                                                      null=True,
                                                      related_name = '%(app_label)s_%(class)s_previous')
    _me_in_previous_subsession_object_id = models.PositiveIntegerField(null=True)

    _me_in_next_subsession_content_type = models.ForeignKey(ContentType,
                                                      null=True,
                                                      related_name = '%(app_label)s_%(class)s_next')
    _me_in_next_subsession_object_id = models.PositiveIntegerField(null=True)

    _me_in_previous_subsession = generic.GenericForeignKey('_me_in_previous_subsession_content_type',
                                                '_me_in_previous_subsession_object_id',)

    _me_in_next_subsession = generic.GenericForeignKey('_me_in_next_subsession_content_type',
                                                '_me_in_next_subsession_object_id',)


    def _start_url(self):
        url = '/{}/{}/{}/{}/'.format(
            self._session_user.user_type_in_url,
            self._session_user.code,
            self.subsession._Constants.name_in_url,
            self._init_view_name,
        )
        return add_params_to_url(url, {constants.user_code: self.code})

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

    _init_view_name = 'InitializeExperimenter'

    class Meta:
        app_label = 'otree'

    @property
    def _session_user(self):
        return self.session_experimenter

    def _pages_as_urls(self):
        return self.subsession._experimenter_pages_as_urls()
