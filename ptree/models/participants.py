from ptree.db import models
import ptree.constants as constants
from ptree.common import currency
import ptree.sessionlib.models
from ptree.common import add_params_to_url
import ptree.models.experiments
from ptree.user.models import User


class BaseParticipant(User):
    """
    Base class for all participants.
    """

    index_among_participants_in_match = models.PositiveIntegerField(null = True)

    session_participant = models.ForeignKey(
        ptree.sessionlib.models.SessionParticipant,
        related_name = '%(app_label)s_%(class)s'
    )

    @property
    def session_user(self):
        return self.session_participant

    def name(self):
        return self.session_participant.__unicode__()

    def __unicode__(self):
        return self.name()

    def start_url(self):
        return add_params_to_url(self.experiment.start_url(), {constants.user_code: self.code})

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
            return 'Error'

    bonus_display.short_description = 'Bonus'

    def sequence_as_urls(self):
        if self.treatment:
            return self.treatment.sequence_as_urls()
        from ptree.views.concrete import WaitUntilAssignedToMatch
        return [WaitUntilAssignedToMatch.url(0)]

    class Meta:
        abstract = True
        ordering = ['pk']

    def add_to_existing_match(self, match):
        self.index_among_participants_in_match = match.participants().count()
        self.match = match
        self.save()

    def add_to_existing_or_new_match(self):
        if not self.match:
            MatchClass = self._meta.get_field('match').rel.to
            match = self.treatment.next_open_match() or ptree.common.create_match(MatchClass, self.treatment)
            self.add_to_existing_match(match)
