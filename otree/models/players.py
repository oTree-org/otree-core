#!/usr/bin/env python
# -*- coding: utf-8 -*-

from otree.models.user import User
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

        qs = type(self).objects.filter(
            participant=self.participant,
            round_number__lt=self.round_number
        ).order_by('round_number')

        return list(qs)

    def in_all_rounds(self):
        return self.in_previous_rounds() + [self]

    def _in_next_round(self):
        return type(self).objects.get(
            participant=self.participant,
            round_number=self.round_number + 1
        )

    def _in_previous_round(self):
        return type(self).objects.get(
            participant=self.participant,
            round_number=self.round_number - 1
        )

    def __unicode__(self):
        return self.name()

    class Meta:
        abstract = True

    def _GroupClass(self):
        return self._meta.get_field('group').rel.to

    @property
    def _Constants(self):
        return get_models_module(self._meta.app_config.name).Constants
