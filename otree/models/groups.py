#!/usr/bin/env python
# -*- coding: utf-8 -*-

from save_the_change.mixins import SaveTheChange

from otree.db import models
from otree.common_internal import get_models_module, get_players


class BaseGroup(SaveTheChange, models.Model):
    """Base class for all Groups.
    """

    _is_missing_players = models.BooleanField(default=False)

    class Meta:
        abstract = True

    def __unicode__(self):
        return str(self.pk)

    _players = []

    def _get_players(self, refresh_from_db=False):
        return get_players(
            self, order_by='id_in_group',
            refresh_from_db=refresh_from_db
        )

    def get_players(self):
        return self._get_players()

    def get_player_by_id(self, id_in_group):
        for p in self.get_players():
            if p.id_in_group == id_in_group:
                return p
        raise ValueError('No player with id_in_group {}'.format(id_in_group))

    def get_player_by_role(self, role):
        for p in self.get_players():
            if p.role() == role:
                return p
        raise ValueError('No player with role {}'.format(role))

    def set_players(self, players_list):
        for i, player in enumerate(players_list, start=1):
            player.group = self
            player.id_in_group = i
            player.save()

    @property
    def _Constants(self):
        return get_models_module(self._meta.app_config.name).Constants
