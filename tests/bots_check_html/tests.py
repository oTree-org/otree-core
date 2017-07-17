from otree.api import Bot, Submission
from . import views
from .models import Constants


class PlayerBot(Bot):

    def play_round(self):
        id_in_group = self.player.id_in_group

        if id_in_group == 1:
            yield views.HtmlMissingFields, {'field_not_in_template': 0.1}
        elif id_in_group == 2:
            yield views.HtmlMissingButton
        else:
            yield Submission(views.TimeoutPage, timeout_happened=True)
