# -*- coding: utf-8 -*-
from __future__ import division
from . import views
from otree.api import Bot
import random


class PlayerBot(Bot):

    def play_round(self):

        self.submit_invalid(
            views.ErrorMessage,
            {'add100_1': 1, 'add100_2': 98}
        )
        yield (views.ErrorMessage, {'add100_1': 1, 'add100_2': 99})
        self.submit_invalid(views.FieldErrorMessage, {'even_int': 1})
        yield (views.FieldErrorMessage, {'even_int': 2})
        self.submit_invalid(views.DynamicChoices, {'dynamic_choices': 'c'})
        yield (
            views.DynamicChoices,
            {'dynamic_choices': random.choice(['a', 'b'])}
        )
        self.submit_invalid(views.MinMax, {'min_max': 2})
        yield (views.MinMax, {'min_max': 5})
        self.submit_invalid(views.DynamicMinMax, {'dynamic_min_max': 4})
        yield (views.DynamicMinMax, {'dynamic_min_max': 3})
        yield (views.Blank)

    def validate_play(self):
        pass
