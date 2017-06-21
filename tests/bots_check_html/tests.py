from otree.api import Bot, Submission

from . import views
from .models import Constants


class PlayerBot(Bot):

    def play_round(self):
        yield Submission(views.Page1, timeout_happened=True)
        yield views.Page2, {'field_not_in_template': 0.1}
