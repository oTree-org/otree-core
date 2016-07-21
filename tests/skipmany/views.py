# -*- coding: utf-8 -*-
from __future__ import division

from otree.common import Currency as c, currency_range, safe_json

from . import models
from ._builtin import Page, WaitPage
from .models import Constants

class SkipMixin(object):
    def is_displayed(self):
        return self.round_number == Constants.num_rounds


class MyPage(Page):
    def is_displayed(self):
        return self.round_number == Constants.num_rounds


class ResultsWaitPage(WaitPage):
    def is_displayed(self):
        return self.round_number == Constants.num_rounds


class Results(Page):
    def is_displayed(self):
        return self.round_number == Constants.num_rounds


page_sequence = [
    MyPage,
    ResultsWaitPage,
    Results
]
