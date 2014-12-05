from otree.models.user import User
import otree.common_internal
from otree.common_internal import get_models_module


class BasePlayer(User):
    """
    Base class for all players.
    """

    @property
    def _session_user(self):
        return self.participant

    # change this to _name? but do we think people will need to refer to names?
    def name(self):
        return self.participant.__unicode__()

    def role(self):
        # you can make this depend of self.id_in_group
        return ''

    def in_previous_rounds(self):

        # FIXME: what if the same app is repeated in subsession_apps? would anyone need to do that?
        # FIXME: add _round_number field to Player
        return type(self).objects.filter(
            participant=self.participant,
            _round_number__lt=self._round_number
        ).order_by('_round_number')

    def in_all_rounds(self):
        return self.in_previous_rounds() + [self]

    def _in_next_round(self):
        return type(self).objects.get(participant=self.participant,round_number=self.round_number+1)

    def __unicode__(self):
        return self.name()

    class Meta:
        abstract = True

    def _assign_to_group(self, group=None):
        if not group:
            group = self.subsession._next_open_group()
        self.group = group
        self.save()
        self.id_in_group = group.player_set.count()
        self.save()

    def _GroupClass(self):
        return self._meta.get_field('group').rel.to

    @property
    def _Constants(self):
        return get_models_module(self._meta.app_label).Constants



