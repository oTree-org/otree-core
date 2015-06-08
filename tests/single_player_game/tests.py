# -*- coding: utf-8 -*-
from __future__ import division
from . import views
from ._builtin import Bot
import random


class PlayerBot(Bot):

    def play_round(self):

        self.submit_invalid(
            views.ErrorMessage,
            {'add100_1': 1, 'add100_2': 98}
        )
        self.submit(views.ErrorMessage, {'add100_1': 1, 'add100_2': 99})
        self.submit_invalid(views.FieldErrorMessage, {'even_int': 1})
        self.submit(views.FieldErrorMessage, {'even_int': 2})
        self.submit_invalid(views.DynamicChoices, {'dynamic_choices': 'c'})
        self.submit(
            views.DynamicChoices,
            {'dynamic_choices': random.choice(['a', 'b'])}
        )
        self.submit_invalid(views.MinMax, {'min_max': 2})
        self.submit(views.MinMax, {'min_max': 5})
        self.submit_invalid(views.DynamicMinMax, {'dynamic_min_max': 4})
        self.submit(views.DynamicMinMax, {'dynamic_min_max': 3})
        self.submit(views.Blank)

    def validate_play(self):
        pass
