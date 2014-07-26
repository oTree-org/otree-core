import random

from django.contrib.contenttypes import generic
from django.contrib.contenttypes.models import ContentType

from ptree.db import models

from ptree.fields import RandomCharField
import ptree.constants as constants
import math
from ptree.common import flatten, ModelWithCheckpointMixin, _views_module
import ptree.user.models
from django.utils.importlib import import_module
import itertools
from django_extensions.db.fields.json import JSONField

class BaseSubsession(models.Model, ModelWithCheckpointMixin):
    """
    Base class for all Subsessions.
    """

    code = RandomCharField(length=8)

    _incomplete_checkpoints = JSONField()

    _experimenter = models.OneToOneField(
        ptree.user.models.Experimenter,
        related_name = '%(app_label)s_subsession',
        null=True)

    _next_subsession_content_type = models.ForeignKey(ContentType,
                                                     null=True,
                                                     related_name = '%(app_label)s_%(class)s_as_next_subsession')
    _next_subsession_object_id = models.PositiveIntegerField(null=True)

    _previous_subsession_content_type = models.ForeignKey(ContentType,
                                                     null=True,
                                                     related_name = '%(app_label)s_%(class)s_as_previous_subsession')

    _previous_subsession_object_id = models.PositiveIntegerField(null=True)


    #FIXME: this should start at 1, to be consistent with index_among_participants_in_match
    _index_in_subsessions = models.PositiveIntegerField(
        null=True,
        doc="starts from 0. indicates the position of this subsession among other subsessions in the session."
    )

    _skip = models.BooleanField(
        default=False,
        doc="""whether the experimenter made the participants skip this subsession"""
    )

    def name(self):
        return str(self.pk)

    def __unicode__(self):
        return self.name()

    def _start_url(self):
        """The URL that a user is redirected to in order to start a treatment.
        3/2/2014: is this still used for anything? i think i am moving towards deprecating it.
        """
        return '/{}/Initialize/?{}={}'.format(self.name_in_url,
                                              constants.user_code,
                                              self.code)

    def previous_round(self):
        s = self
        while True:
            s = s.previous_subsession
            if not s:
                return None
            if s.app_name() == self.app_name():
                return s

    def _picked_treatments(self):
        return [m.treatment for m in self.match_set.all()]

    def pick_treatments(self, previous_round_treatments):
        return previous_round_treatments

    def pick_match_groups(self, previous_round_match_groups):
        return previous_round_match_groups

    def _next_open_match(self):
        """Get the next match that is accepting participants.
        (or none if it does not exist)
        """
        try:
            return (m for m in self.match_set.all() if m._is_ready_for_next_participant()).next()
        except StopIteration:
            return None

    def _num_matches(self):
        """number of matches in this subsession"""
        return self.participant_set.count()/self._MatchClass().participants_per_match

    def _random_treatments(self):
        num_matches = self._num_matches()
        treatments = list(self.treatment_set.all())
        random.shuffle(treatments)
        iterator = itertools.cycle(treatments)
        random_treatments = []
        for i in range(num_matches):
            random_treatments.append(iterator.next())
        return random_treatments

    def _random_match_groups(self):
        participants = list(self.participant_set.all())
        random.shuffle(participants)
        match_groups = []
        participants_per_match = self._MatchClass().participants_per_match
        for i in range(self._num_matches()):
            start_index = i*participants_per_match
            end_index = start_index + participants_per_match
            match_groups.append(participants[start_index:end_index])
        return match_groups

    def _corresponding_treatments(self, earlier_round):
        earlier_treatment_indexes = [t._index_within_subsession for t in earlier_round._picked_treatments()]
        current_treatments = list(self.treatment_set.all())
        return [current_treatments[i] for i in earlier_treatment_indexes]

    def _match_groups(self):
        return [list(m.participant_set.all()) for m in self.match_set.all()]

    def _corresponding_match_groups(self, earlier_round):
        current_participant_dict = {p.session_participant.pk: p for p in self.participant_set.all()}
        match_groups = earlier_round._match_groups()
        for m_index, m in enumerate(match_groups):
            for p_index, p in enumerate(m):
                match_groups[m_index][p_index] = current_participant_dict[p.session_participant.pk]
        return match_groups

    def _MatchClass(self):
        return import_module('{}.models'.format(self._meta.app_label)).Match

    def _create_empty_matches(self):
        self._initialize_checkpoints()
        self.save()
        previous_round = self.previous_round()
        if previous_round:
            treatments = self._corresponding_treatments(previous_round)
        else:
            treatments = self._random_treatments()
        treatments = self.pick_treatments(treatments)
        MatchClass = self._MatchClass()
        for t in treatments:
            m = MatchClass._create(t)

    def _assign_participants_to_matches(self):
        previous_round = self.previous_round()
        if previous_round:
            match_groups = self._corresponding_match_groups(previous_round)
        else:
            match_groups = self._random_match_groups()
        match_groups = self.pick_match_groups(match_groups)
        for match_group in match_groups:
            match = self._next_open_match()
            for participant in match_group:
                participant._assign_to_match(match)
            match._initialize_checkpoints()
            match.save()

    def previous_subsession_is_in_same_app(self):
        previous_subsession = self.previous_subsession
        return previous_subsession and previous_subsession._meta.app_label == self._meta.app_label

    def _experimenter_pages(self):
        views_module = _views_module(self)
        if hasattr(views_module, 'experimenter_pages'):
            return views_module.experimenter_pages() or []
        return []

    def _experimenter_pages_as_urls(self):
        """Converts the sequence to URLs.

        e.g.:
        pages() returns something like [views.IntroPage, ...]
        pages_as_urls() returns something like ['mygame/IntroPage', ...]
        """
        return [View.url(self._experimenter.session_experimenter, index) for index, View in enumerate(self._experimenter_pages())]

    def _CheckpointMixinClass(self):
        from ptree.views.abstract import SubsessionCheckpointMixin
        return SubsessionCheckpointMixin


    class Meta:
        abstract = True