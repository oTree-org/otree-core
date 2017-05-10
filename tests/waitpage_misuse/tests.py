# -*- coding: utf-8 -*-
from __future__ import division, absolute_import
from . import views
from otree.api import Bot


class PlayerBot(Bot):

    def play_round(self):
        yield views.Page1
