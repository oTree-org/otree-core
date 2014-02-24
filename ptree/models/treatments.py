from ptree.db import models
from ptree.fields import RandomCharField
import ptree.constants as constants
from ptree.common import id_label_name
import ptree.sessionlib.models

class BaseTreatment(models.Model):
    """
    Base class for all Treatments.
    """

    label = models.CharField(max_length = 300, null = True, blank = True)

    session = models.ForeignKey(ptree.sessionlib.models.Session,
                                                null=True,
                                                related_name = '%(app_label)s_%(class)s')

    # the treatment code in the URL. This is generated automatically.
    code = RandomCharField(length=8)

    participants_per_match = models.PositiveIntegerField(default=1)


    def start_url(self):
        """The URL that a user is redirected to in order to start a treatment"""
        return '/{}/Initialize/?{}={}'.format(self.subsession.name_in_url,
                                      constants.treatment_code,
                                      self.code)

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

    def matches(self):
        return list(self.match_set.all())

    def participants(self):
        return list(self.participant_set.all())

    def pages(self):
        raise NotImplementedError()

    def pages_as_urls(self):
        # 2/11/2014: start at 1 because i added the wait page (until assigned to match)
        # maybe should clean this up.
        # 2/22/2014: i shouldn't have WaitUntilAssignedToMatch because if they were assigned to a match & treatment,
        # they wouldn't access this in the first place.
        # but this must still work if you look up an element.
        from ptree.views.concrete import WaitUntilAssignedToMatch
        all_views = [WaitUntilAssignedToMatch] + self.pages()
        return [View.url(index) for index, View in enumerate(all_views)]

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