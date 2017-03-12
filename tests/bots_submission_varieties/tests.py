from __future__ import division

from otree.api import Bot, Submission, SubmissionMustFail

from . import views
from .models import Constants


class PlayerBot(Bot):
    '''Testing the different syntaxes for submits'''

    def play_round(self):
        yield Submission(views.Page1)
        yield SubmissionMustFail(views.Page2, check_html=False)
        yield Submission(views.Page2, {'f2': True}, check_html=False)
        yield SubmissionMustFail(views.Page3, {})
        yield Submission(views.Page3, {'f3': True})
