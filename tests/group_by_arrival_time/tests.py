from . import views
from .models import Constants
from otree.api import Bot
import time

class PlayerBot(Bot):

    def play_round(self):
        # add these in later
        assert self.group.set_in_wait_page == True, self.group.id
        assert self.player.set_in_wait_page == True

        yield views.Page1

        for attempt in [1, 2, 3]:
            try:
                self.run_assertions()
                break
            except AssertionError:
                if attempt == 3:
                    raise
                else:
                    # a little cushion to reduce race conditions
                    time.sleep(3)

    def run_assertions(self):
        # Race condition: this might be evaluated before all players finish
        # currently it works, but if i change the order that bots run,
        # it might not work in the future.
        # for now, this is the simplest way to get it working with browser bots
        # because there is no validate_play method. (usually its not needed)
        # it's non-trivial to make a validate_play that works with browser bots
        # because they run in a distributed way.
        # i could change this to run just for each individual player like the
        # run_assertions() methods in the other GBAT games, but I don't know
        # any way to ensure there are no empty groups. is that important?
        num_players = self.subsession.player_set.count()
        if self.player.id_in_subsession == num_players and self.round_number == Constants.num_rounds:
            for subsession in self.subsession.in_all_rounds():
                groups = subsession.get_groups()
                players = subsession.get_players()
                for group in groups:
                    assert len(group.get_players()) == Constants.players_per_group, self.subsession.round_number
                assert len(groups) == len(players) / Constants.players_per_group

