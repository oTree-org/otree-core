from django.contrib.contenttypes import generic
from django.contrib.contenttypes.models import ContentType

from ptree.fields import RandomCharField
from ptree.db import models
import ptree.constants as constants
from ptree.common import add_params_to_url

class User(models.Model):
    """represents experimenter or participants"""
    # the participant's unique ID (and redemption code) that gets passed in the URL.
    code = RandomCharField(length = 8)

    visited = models.BooleanField(default=False)

    def pages_as_urls(self):
        raise NotImplementedError()

    session = models.ForeignKey(
        'sessionlib.Session',
        related_name = '%(app_label)s_%(class)s')

    index_in_pages = models.PositiveIntegerField(default=0)

    # 2/12/2014: i think the previous pointer is unnecessary because i can traverse via the reverse relation of the "next" pointer
    me_in_previous_subsession_content_type = models.ForeignKey(ContentType,
                                                      null=True,
                                                      related_name = '%(app_label)s_%(class)s_previous')
    me_in_previous_subsession_object_id = models.PositiveIntegerField(null=True)
    me_in_previous_subsession = generic.GenericForeignKey('me_in_previous_subsession_content_type',
                                                'me_in_previous_subsession_object_id',)

    me_in_next_subsession_content_type = models.ForeignKey(ContentType,
                                                      null=True,
                                                      related_name = '%(app_label)s_%(class)s_next')
    me_in_next_subsession_object_id = models.PositiveIntegerField(null=True)
    me_in_next_subsession = generic.GenericForeignKey('me_in_next_subsession_content_type',
                                                'me_in_next_subsession_object_id',)


    def _start_url(self):
        url = '/{}/{}/{}/{}/'.format(
            self._session_user.user_type_in_url,
            self._session_user.code,
            self.subsession.name_in_url,
            self._init_view_name,
        )
        return add_params_to_url(url, {constants.user_code: self.code})

    class Meta:
        abstract = True

class Experimenter(User):

    session_experimenter = models.ForeignKey(
        'sessionlib.SessionExperimenter',
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

    @property
    def _session_user(self):
        return self.session_experimenter

    def pages_as_urls(self):
        return self.subsession._experimenter_pages_as_urls()
