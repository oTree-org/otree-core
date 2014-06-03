from ptree.user.models import User


class BaseParticipant(User):
    """
    Base class for all participants.
    """

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

    def _add_to_existing_match(self, match):
        self.match = match
        self.save()
        self.index_among_participants_in_match = match.participant_set.count()
        self.save()

    def _add_to_existing_or_new_match(self):
        if not self.match:
            MatchClass = self._meta.get_field('match').rel.to
            match = self.treatment._next_open_match() or MatchClass._create(self.treatment, self.subsession)
            self._add_to_existing_match(match)

    def _pages_completed(self):
        if not (self.treatment and self.visited):
            return None
        return '{}/{} pages'.format(
            self.index_in_pages,
            len(self._pages())
        )