from ptree.user.models import User


class BaseParticipant(User):
    """
    Base class for all participants.
    """

    def _me_in_other_subsession(self, other_subsession):
        for p in other_subsession.participant_set.all():
            if p.session_participant == self.session_participant:
                return p

    @property
    def _session_user(self):
        return self.session_participant

    # change this to _name? but do we think people will need to refer to names?
    def name(self):
        return self.session_participant.__unicode__()

    def __unicode__(self):
        return self.name()

    _init_view_name = 'InitializeParticipant'

    def _pages(self):
        """if a user really wants to make the pages dynamic, more than is possible with show_skip_wait, they can override this method.
        """
        views_module = self.subsession._views_module()
        return views_module.pages()

    def _pages_as_urls(self):
        from ptree.views.concrete import WaitUntilAssignedToMatch
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
        self.index_among_participants_in_match = match.participant_set.count()
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