from otree.db import models
import otree.sessionlib.models
from save_the_change.mixins import SaveTheChange
from django_extensions.db.fields.json import JSONField

class BaseGroup(SaveTheChange, models.Model):
    """
    Base class for all Groupes.
    """

    def __unicode__(self):
        return str(self.pk)

    def _is_ready_for_next_player(self):
        return len(self.player_set.all()) < self.players_per_group

    def get_player_by_id(self, id_):
        for p in self.get_players():
            if p.id_in_group == id_:
                return p

    def get_player_by_role(self, role):
        for p in self.get_players():
            if p.role() == role:
                return p

    @classmethod
    def _create(cls, subsession):
        group = cls(
            subsession = subsession,
            session = subsession.session
        )
        # need to save it before you assign the player.group ForeignKey
        group.save()
        return group

    class Meta:
        abstract = True