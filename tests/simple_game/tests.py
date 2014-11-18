# -*- coding: utf-8 -*-
from __future__ import division
from . import views
from ._builtin import Bot
import random
from otree.common import Currency, currency_range
from .models import Constants


class PlayerBot(Bot):

    def play(self):

        self.submit(views.MyPage, {'add100_1': 1, 'add100_2': 99})
        self.submit(views.Results)