from otree.db import models
import otree.sessionlib.models
from save_the_change.mixins import SaveTheChange
from django_extensions.db.fields.json import JSONField

class BaseMatch(SaveTheChange, models.Model):
    """
    Base class for all Matches.
    """

    def __unicode__(self):
        return str(self.pk)

    def _is_ready_for_next_player(self):
        return len(self.player_set.all()) < self.players_per_match

    def get_player_by_index(self, index):
        for p in self.players:
            if p.id_in_match == index:
                return p

    def get_player_by_role(self, role):
        for p in self.players:
            if p.role() == role:
                return p

    @classmethod
    def _create(cls, subsession):
        match = cls(
            subsession = subsession,
            session = subsession.session
        )
        # need to save it before you assign the player.match ForeignKey
        match.save()
        return match

    class Meta:
        abstract = True