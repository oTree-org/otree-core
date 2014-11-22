# -*- coding: utf-8 -*-
from __future__ import division

import random

from otree.common import Currency, currency_range

from . import views
from ._builtin import Bot
from .models import Constants


class PlayerBot(Bot):
    """Bot that plays one round"""

    def play(self):
        pass

    def validate_play(self):
        pass
