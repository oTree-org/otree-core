from ptree.db import models
import ptree.sessionlib.models

class BaseMatch(models.Model):
    """
    Base class for all Matches.
    """

    session = models.ForeignKey(ptree.sessionlib.models.Session,
                                                related_name = '%(app_label)s_%(class)s')


    def __unicode__(self):
        return str(self.pk)

    def is_ready_for_next_participant(self):
        return len(self.participants()) < self.treatment.participants_per_match

    """
    def participants(self):
        if hasattr(self, '_participants'):
            return self._participants
        self._participants = list(self.participant_set.order_by('index_among_participants_in_match'))
        return self._participants
    """

    def participants(self):
        return list(self.participant_set.all())

    @classmethod
    def create(cls, treatment):
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
        verbose_name_plural = "matches"
        ordering = ['pk']