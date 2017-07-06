from otree.api import (
    Currency as c, currency_range, Submission, SubmissionMustFail)
from . import views
from ._builtin import Bot
from .models import Constants


class PlayerBot(Bot):

    def play_round(self):
        '''all args should autocomplete'''

        yield SubmissionMustFail(
            views.Page1,
            {'a': 1},
            check_html=True)

        yield Submission(
            views.Page1,
            {'a': 1},
            check_html=False,
            timeout_happened=True)
