# -*- coding: utf-8 -*-
from __future__ import division

from otree.api import Bot

from . import views
from .models import Constants


class PlayerBot(Bot):

    def play_round(self):
        yield views.Page1
        yield views.Page2

        # important to know that the bot executes code past the last yield
        raise ZeroDivisionError
