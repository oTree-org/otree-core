# -*- coding: utf-8 -*-
from __future__ import division

from otree.api import Bot

from . import views
from .models import Constants


class PlayerBot(Bot):

    cases = ['case1', 'case2']

    def case1(self):
        pass

    def case2(self):
        pass

    def play_round(self):
        if self.case == 'case1':
            self.case1()
        if self.case == 'case2':
            self.case2()

        yield views.Page1
