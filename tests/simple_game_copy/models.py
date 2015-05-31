# -*- coding: utf-8 -*-
# <standard imports>
from __future__ import division
from otree.db import models
import otree.models
from otree import widgets
from otree.common import Currency, currency_range
import random
# </standard imports>

class Constants:
    name_in_url = 'simple_game_copy'
    players_per_group = None
    num_rounds = 1



author = 'Your name here'

doc = """
Description of this app.
"""


class Subsession(otree.models.BaseSubsession):

    name_in_url = 'simple_game_copy'


class Group(otree.models.BaseGroup):
    # <built-in>
    subsession = models.ForeignKey(Subsession)
    # </built-in>

    players_per_group = None

    def set_payoffs(self):
        for p in self.get_players():
            p.payoff = 0 # change to whatever the payoff should be


class Player(otree.models.BasePlayer):
    # <built-in>
    subsession = models.ForeignKey(Subsession)
    group = models.ForeignKey(Group, null = True)
    # </built-in>

    def other_player(self):
        """Returns other player in group. Only valid for 2-player groups."""
        return self.get_others_in_group()[0]

    # example field
    my_field = models.CurrencyField(
        doc="""
        Description of this field, for documentation
        """
    )

    def my_field_bounds(self):
        return [5, 10]

    add100_1 = models.PositiveIntegerField()
    add100_2 = models.PositiveIntegerField()

    even_int = models.PositiveIntegerField()

    before_next_page_field = models.BooleanField()

    def even_int_error_message(self, value):
        if value % 2:
            return 'Must be an even number'

    def role(self):
        # you can make this depend of self.id_in_group
        return ''
