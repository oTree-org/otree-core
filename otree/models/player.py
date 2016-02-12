#!/usr/bin/env python
# -*- coding: utf-8 -*-

from otree.common_internal import get_models_module
from otree_save_the_change.mixins import SaveTheChange

from otree.db import models
from otree.models.session import Session


class BasePlayer(SaveTheChange, models.Model):
    """
    Base class for all players.
    """

    class Meta:
        abstract = True
        index_together = ['participant', 'round_number']
        ordering = ['pk']

    _index_in_game_pages = models.PositiveIntegerField(
        default=0,
        doc='Index in the list of pages  views_module.page_sequence'
    )

    session = models.ForeignKey(
        Session, related_name='%(app_label)s_%(class)s'
    )

    round_number = models.PositiveIntegerField(db_index=True)

    # it's _name instead of name because people might define
    # their own name field
    def _name(self):
        return self.participant.__unicode__()

    def role(self):
        # you can make this depend of self.id_in_group
        return ''

    def in_round(self, round_number):
        return type(self).objects.get(
            participant=self.participant,
            round_number=round_number
        )

    def in_rounds(self, first, last):
        qs = type(self).objects.filter(
            participant=self.participant,
            round_number__gte=first,
            round_number__lte=last,
        ).order_by('round_number')

        return list(qs)

    def in_previous_rounds(self):
        return self.in_rounds(1, self.round_number - 1)

    def in_all_rounds(self):
        return self.in_previous_rounds() + [self]

    def __unicode__(self):
        return self._name()

    def _GroupClass(self):
        return self._meta.get_field('group').rel.to

    @property
    def _Constants(self):
        return get_models_module(self._meta.app_config.name).Constants
