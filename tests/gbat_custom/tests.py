# -*- coding: utf-8 -*-
from __future__ import division, absolute_import
from . import views
from .models import Constants
from otree.api import Bot
from ..gbat_round1.tests import GBATMixin


class PlayerBot(Bot, GBATMixin):

    def play_round(self):
        p1, p2 = self.group.get_players()
        assert p1.type == 'A'
        assert p2.type == 'B'

        # are these tests redundant? keep them for now, until i can prove
        # they are not needed
        self.run_assertions()

        yield views.Page1


