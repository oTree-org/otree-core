from __future__ import division
from otree.api import (
    BaseSubsession, BaseGroup, BasePlayer, BaseConstants, models,
    Currency
)


doc = """
Bot that doesn't submit anything. In some apps, a given player might skip all pages.
Make sure this doesn't cause a TypeError because play_round doesn't yield anything,
so it isn't considered iterable.
"""


class Constants(BaseConstants):
    name_in_url = 'bots_empty'
    players_per_group = None
    num_rounds = 1


class Subsession(BaseSubsession):
    pass


class Group(BaseGroup):
    pass


class Player(BasePlayer):
    pass
