# -*- coding: utf-8 -*-
from __future__ import division
from . import views
from ._builtin import Bot
import random
from otree.common import Currency, currency_range
from .models import Constants


class PlayerBot(Bot):

    def play_round(self):

        self.submit_invalid(views.ErrorMessage, {'add100_1': 1, 'add100_2': 98})
        self.submit(views.ErrorMessage, {'add100_1': 1, 'add100_2': 99})
        self.submit_invalid(views.FieldErrorMessage, {'even_int': 1})
        self.submit_invalid(views.FieldErrorMessage, {'even_int': 2})
        self.submit(views.MinMax, {'min_max': 5})
        self.submit_invalid(views.DynamicChoices, {'dynamic_choices': 'c'})
        self.submit(views.DynamicChoices, {'dynamic_choices': random.choice(['a','b'])})
        self.submit(views.Blank)
        self.submit(views.Results)

    def validate_play(self):
        pass