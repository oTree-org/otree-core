from otree.api import Currency as c, currency_range
from . import pages
from ._builtin import Bot
from .models import Constants
import random
from random import randint
from otree.api import Submission

class PlayerBot(Bot):

    def number_of_shares_max(self):
        if self.player.round_number == 1:
            return int((Constants.max_borrow + Constants.endowment) / self.player.fv)
        else:
            if self.player.in_round(self.player.round_number - 1).wallet > 0:
                return int((Constants.max_borrow + self.player.in_round(self.player.round_number - 1).wallet) /
                        self.player.in_round(self.player.round_number - 1).price)
            else:
                return int((Constants.max_borrow / self.player.in_round(self.player.round_number - 1).price))

    def play_round(self):
        if self.subsession.round_number == 1:
            yield (pages.Introduction)
        else:
            pass

        if self.subsession.round_number < Constants.bot_steps + 1:
            print(self.player.round_number,self.subsession.round_number)
            yield (pages.Steps, {'choice_of_steps': self.player.round_number - 1})
        else:
            yield (pages.Steps, {'choice_of_steps': Constants.bot_steps})

        dh = sum([p.choice_of_majority for p in self.player.in_rounds(
            self.player.round_number - self.player.choice_of_steps - 1, self.player.round_number - 1)])

        if random.random() < Constants.p_ego:
            yield (pages.Choose, {'choice_of_trade': DecisionRule.ego_rule(
                    self.player.current_item), 'choice_of_number_of_shares': randint(0, self.number_of_shares_max())})
        else:
            yield (pages.Choose, {'choice_of_trade': DecisionRule.bayes_rule(
                    self.player.current_item, self.player.choice_of_steps, dh),
                        'choice_of_number_of_shares': randint(0, self.number_of_shares_max())})

        print(self.player.price)
        if self.player.price < 1:
            yield Submission(pages.Delisted, check_html=False)
        else:
            pass

        yield (pages.Results)


class DecisionRule(object):
    """Various decision rules for a player in the sequence."""

    def ego_rule(self):
        return self                     # private signal decides

    def duffle_rule(self):  # player goes with public majority, private if tie
                            # duffle: see Cat's Cradle chapter 89
        if sum(decision_history) > len(decision_history)/2: # True = 1, False = 0
            return True                 # if public majority thinks True return True
        elif sum(decision_history) == len(decision_history)/2:
            return self                 # if public majority tied, return private signal
            # return not self             # if public majority tied, return opposite of private signal
            # return bool(random.getrandbits(1)) # if public majority tied, return random signal
        else:
            return False                # if public majority thinks False return False

    def bayes_rule(self, decision_length, decision_history): # player goes for absolute majority, private if tie
        if decision_history + self >  (decision_length + 1)/2: # True = 1, False = 0
            return True                 # if absolute majority thinks True return True
        elif decision_history + self == (decision_length + 1)/2:
            return self                     # if absolute majority tied, return private signal
            # return not self                 # if absolute majority tied, return opposite of private signal
            # return bool(random.getrandbits(1)) # if absolute majority tied, return random signal
        else:
            return False                # if absolute majority thinks False return False