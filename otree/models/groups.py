#!/usr/bin/env python
# -*- coding: utf-8 -*-

from save_the_change.mixins import SaveTheChange

from otree.db import models
from otree.common_internal import get_models_module, get_players
from idmap.models import SharedMemoryModel

class BaseGroup(SaveTheChange, SharedMemoryModel):
    """Base class for all Groups.
    """

    _is_missing_players = models.BooleanField(default=False)

    class Meta:
        abstract = True

    def __unicode__(self):
        return str(self.pk)

    _players = []
    _player = None

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

    def get_player_by_role(self, role):
        for p in self.get_players():
            if p.role() == role:
                return p

    def set_players(self, players_list):
        for i, player in enumerate(players_list, start=1):
            player.group = self
            player.id_in_group = i
            player.save()

    @property
    def _Constants(self):
        return get_models_module(self._meta.app_label).Constants
