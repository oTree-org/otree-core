import random

from django.contrib.contenttypes import generic
from django.contrib.contenttypes.models import ContentType

from ptree.db import models

from ptree.fields import RandomCharField
import ptree.constants as constants

from ptree.common import id_label_name
import ptree.user.models


class BaseSubsession(models.Model):
    """
    Base class for all Subsessions.
    """

    code = RandomCharField(length=8)

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
    _index_in_subsessions = models.PositiveIntegerField(null=True)

    _skip = models.BooleanField(default=False)

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


    def pick_treatment_with_open_match(self):
        return [m for m in self.matches() if m._is_ready_for_next_participant()][0].treatment

    def pick_treatment_for_incoming_participant(self):
        try:
            return self.pick_treatment_with_open_match()
        except IndexError:
            treatments = list(self.treatments())
            random.shuffle(treatments)
            return min(treatments, key=lambda treatment: len(treatment.participants()))

    def _assign_participants_to_treatments_and_matches(self):
        participants = self.participants()[:]
        random.shuffle(participants)
        for participant in participants:
            participant.treatment = self.pick_treatment_for_incoming_participant()
            participant._add_to_existing_or_new_match()
            participant.save()

    def previous_subsession_is_in_same_app(self):
        previous_subsession = self.previous_subsession
        return previous_subsession and previous_subsession._meta.app_label == self._meta.app_label

    def _assign_participants_to_same_treatment_as_previous_subsession(self):
        previous_subsession = self.previous_subsession
        assert self.previous_subsession_is_in_same_app()
        treatments = self.treatments()
        previous_treatments = previous_subsession.treatments()
        old_to_new_treatments = dict(zip(previous_treatments, treatments))

        previous_participants = previous_subsession.participants()
        participants = self.participants()
        for i, participant in enumerate(participants):
            previous_participant = previous_participants[i]
            previous_treatment = previous_participant.treatment
            participant.treatment = old_to_new_treatments[previous_treatment]
            participant._add_to_existing_or_new_match()
            participant.save()


    """
    def treatments(self):
        if hasattr(self, '_treatments'):
            return self._treatments
        self._treatments = list(self.treatment_set.all())
        return self._treatments

    def matches(self):
        if hasattr(self, '_matches'):
            return self._matches
        self._matches = list(self.match_set.all())
        return self._matches

    def participants(self):
        if hasattr(self, '_participants'):
            return self._participants
        self._participants = list(self.participant_set.all())
        return self._participants
    """


    def _experimenter_pages_as_urls(self):
        """Converts the sequence to URLs.

        e.g.:
        sequence() returns something like [views.IntroPage, ...]
        pages_as_urls() returns something like ['mygame/IntroPage', ...]
        """
        return [View.url(self._experimenter.session_experimenter, index) for index, View in enumerate(self.experimenter_pages())]

    class Meta:
        abstract = True