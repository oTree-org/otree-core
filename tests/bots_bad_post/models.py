# -*- coding: utf-8 -*-
# <standard imports>
from __future__ import division
from otree.api import (
    BaseSubsession, BaseGroup, BasePlayer, BaseConstants, models,
    Currency
)

# </standard imports>

doc = """
Testing functionality of the bots themselves
"""

class Constants(BaseConstants):
    name_in_url = 'bots_bad_post'
    players_per_group = None
    num_rounds = 1


class Subsession(BaseSubsession):
    pass


class Group(BaseGroup):
    pass


class Player(BasePlayer):
    my_field = models.PositiveIntegerField(choices=[1,2])
