from otree.api import (
    Currency as c, currency_range, SubmissionMustFail, Submission
)
from . import views
from ._builtin import Bot
from .models import Constants


class PlayerBot(Bot):
    pass
