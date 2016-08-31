# -*- coding: utf-8 -*-
from __future__ import division

from otree.api import Bot, Submission

from . import views
from .models import Constants


class PlayerBot(Bot):

    def play_round(self):
        yield (views.Page1, {'my_field': 0.1})
