from otree.user.models import User
import otree.common

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

    def me_in_previous_rounds(self):

        players = []
        current_player = self
        for i in range(self.subsession.round_number-1):
            current_player = current_player._me_in_previous_subsession
            players.append(current_player)
        # return starting with round 1
        players.reverse()
        return players


    def __unicode__(self):
        return self.name()

    _init_view_name = 'InitializePlayer'

    def _pages(self):
        """
        FIXME: deprecate and remove.
        if a user really wants to make the pages dynamic, more than is possible with show_skip_wait, they can override this method.
        """
        views_module = otree.common._views_module(self)
        return views_module.pages()

    def _pages_as_urls(self):
        from otree.views.concrete import WaitUntilAssignedToMatch
        all_views = [WaitUntilAssignedToMatch] + self._pages()
        return [View.url(self._session_user, index) for index, View in enumerate(all_views)]

    class Meta:
        abstract = True

    def _assign_to_match(self, match=None):
        if not match:
            match = self.subsession._next_open_match()
        self.match = match
        self.treatment = match.treatment
        self.save()
        self.index_among_players_in_match = match.player_set.count()
        self.save()

    def _MatchClass(self):
        return self._meta.get_field('match').rel.to

    def _pages_completed(self):
        if not (self.treatment and self.visited):
            return None
        return '{}/{} pages'.format(
            self.index_in_pages,
            len(self._pages())
        )