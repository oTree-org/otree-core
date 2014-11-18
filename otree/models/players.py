from otree.models.user import User
import otree.common_internal
from otree.common_internal import get_models_module


class BasePlayer(User):
    """
    Base class for all players.
    """



    def _me_in_other_subsession(self, other_subsession):
        for p in other_subsession.player_set.all():
            if p.participant == self.participant:
                return p

    @property
    def _session_user(self):
        return self.participant

    # change this to _name? but do we think people will need to refer to names?
    def name(self):
        return self.participant.__unicode__()

    def role(self):
        # you can make this depend of self.id_in_group
        return ''

    def me_in_previous_rounds(self):

        players = []
        current_player = self
        for i in range(self.subsession.round_number-1):
            current_player = current_player._me_in_previous_subsession
            players.append(current_player)
        # return starting with round 1
        players.reverse()
        return players

    def me_in_all_rounds(self):
        return self.me_in_previous_rounds() + [self]

    def __unicode__(self):
        return self.name()

    _init_view_name = 'InitializePlayer'

    def _pages(self):
        from otree.views.concrete import WaitUntilAssignedToGroup
        views_module = otree.common_internal._views_module(self)
        return [WaitUntilAssignedToGroup] + views_module.pages()

    def _pages_as_urls(self):
        return [View.url(self._session_user, index) for index, View in enumerate(self._pages())]

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


    def _pages_completed(self):
        if not self.visited:
            return None
        return '{}/{} pages'.format(
            self.index_in_pages,
            len(self._pages())
        )

