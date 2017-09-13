from . import views
from .models import Constants
from otree.api import Bot
from unittest import TestCase


class PlayerBot(Bot):

    def play_round(self):
        # add these in later
        assert self.group.set_in_wait_page == True, self.group.id
        assert self.player.set_in_wait_page == True

        yield views.Page1

        self.run_assertions()

    def run_assertions(self):
        if self.round_number == Constants.num_rounds:
            for p in self.player.in_all_rounds():
                assert p.group.player_set.count() == Constants.players_per_group
