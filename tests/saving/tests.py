from __future__ import division
from . import views
from otree.api import Bot, SubmissionMustFail, Currency as c
import random


class PlayerBot(Bot):
    def play_round(self):
        yield views.Start
        yield views.IsDisplayed
        yield views.End
