# -*- coding: utf-8 -*-
# <standard imports>
from __future__ import division
from otree.db import models
import otree.models
from otree import widgets
from otree.common import Currency, currency_range
import random
# </standard imports>

doc = "foo"

class Constants:
    name_in_url = 'simple_game_copy'
    players_per_group = None
    num_rounds = 1


class Subsession(otree.models.BaseSubsession):
    pass


class Group(otree.models.BaseGroup):
    # <built-in>
    subsession = models.ForeignKey(Subsession)
    # </built-in>

    players_per_group = None

    def set_payoffs(self):
        for p in self.get_players():
            p.payoff = 0


class Player(otree.models.BasePlayer):
    # <built-in>
    subsession = models.ForeignKey(Subsession)
    group = models.ForeignKey(Group, null = True)
    # </built-in>

    my_field = models.CurrencyField()
