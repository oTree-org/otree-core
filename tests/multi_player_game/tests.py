# -*- coding: utf-8 -*-
from __future__ import division
from . import views
from ._builtin import Bot


class PlayerBot(Bot):

    def play_round(self):

        if self.player.id_in_group == 1:
            self.submit(views.FieldOnOtherPlayer)
        self.submit(views.Results)

    def validate_play(self):
        pass
