from ptree.db import models
from ptree.fields import RandomCharField
import ptree.constants as constants
from ptree.common import id_label_name
import ptree.sessionlib.models
from importlib import import_module

django_models = import_module('django.db.models')

class BaseTreatment(django_models.Model):
    """
    Base class for all Treatments.
    """

    # the treatment code in the URL. This is generated automatically.
    _code = RandomCharField(length=8)

    _index_within_subsession = models.PositiveIntegerField(
        null=True,
    )

    @classmethod
    def create(cls, *args, **kwargs):
        """public API, used in models.py"""
        return cls(*args, **kwargs)

    # 3/7/2014: get rid of this? we don't have URLs for treatments anymore.
    def _start_url(self):
        """The URL that a user is redirected to in order to start a treatment"""
        return '/{}/Initialize/?{}={}'.format(self.subsession.name_in_url,
                                      constants.treatment_code,
                                      self._code)

    def name(self):
        return id_label_name(self.pk, self.label)

    def __unicode__(self):
        return self.name()

    """
    def matches(self):
        if hasattr(self, '_matches'):
            return self._matches
        self._matches = list(self.match_set.all())
        return self._matches

    def participants(self):
        if hasattr(self, '_participants'):
            return self._participants
        self._participants = list(self.participant_set.all())
        return self._participants
    """




    class Meta:
        abstract = True