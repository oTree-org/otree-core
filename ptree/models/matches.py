from ptree.db import models
import ptree.sessionlib.models
from save_the_change.mixins import SaveTheChange

class BaseMatch(SaveTheChange, models.Model):
    """
    Base class for all Matches.
    """

    def __unicode__(self):
        return str(self.pk)

    def _is_ready_for_next_participant(self):
        return len(self.participants()) < self.participants_per_match

    """
    def participants(self):
        if hasattr(self, '_participants'):
            return self._participants
        self._participants = list(self.participant_set.order_by('index_among_participants_in_match'))
        return self._participants
    """


    @classmethod
    def _create(cls, treatment):
        match = cls(
            treatment = treatment,
            subsession = treatment.subsession,
            session = treatment.session
        )
        # need to save it before you assign the participant.match ForeignKey
        match.save()
        return match

    class Meta:
        abstract = True