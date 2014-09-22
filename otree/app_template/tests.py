from __future__ import division
import {{ app_name }}.views as views
from {{ app_name }}._builtin import Bot
from otree.common import Money, money_range

class PlayerBot(Bot):

    def play(self):
        pass