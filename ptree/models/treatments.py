from django.http import HttpResponseRedirect
from ptree.db import models
from ptree.fields import RandomCharField
import ptree.constants as constants
from ptree.common import id_label_name
import ptree.session.models

class BaseTreatment(models.Model):
    """
    Base class for all Treatments.
    """

    label = models.CharField(max_length = 300, null = True, blank = True)

    session = models.ForeignKey(ptree.session.models.Session,
                                                null=True,
                                                related_name = '%(app_label)s_%(class)s')

    # the treatment code in the URL. This is generated automatically.
    code = RandomCharField(length=8)

    participants_per_match = models.PositiveIntegerField(default=1)


    def start_url(self):
        """The URL that a user is redirected to in order to start a treatment"""
        return '/{}/Initialize/?{}={}'.format(self.experiment.name_in_url,
                                      constants.treatment_code,
                                      self.code)

    def name(self):
        return id_label_name(self.pk, self.label)

    def __unicode__(self):
        return self.name()

    def matches(self):
        return self.match_set.all()

    def participants(self):
        return self.participant_set.all()

    def sequence_of_views(self):
        raise NotImplementedError()

    def sequence_as_urls(self):
        """Converts the sequence to URLs.

        e.g.:
        sequence() returns something like [views.IntroPage, ...]
        sequence_as_urls() returns something like ['mygame/IntroPage', ...]
        """
        return [View.url(index) for index, View in enumerate(self.sequence_of_views())]

    def next_open_match(self):
        """Get the next match that is accepting participants.
        (or none if it does not exist)
        """
        try:
            return (m for m in self.matches() if m.is_ready_for_next_participant()).next()
        except StopIteration:
            return None


    class Meta:
        abstract = True
        ordering = ['pk']