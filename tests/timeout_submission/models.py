# -*- coding: utf-8 -*-
# <standard imports>
from __future__ import division
from otree.api import (
    BaseSubsession, BaseGroup, BasePlayer, BaseConstants, models
)
# </standard imports>

doc = ""

class Constants(BaseConstants):
    name_in_url = 'timeout'
    players_per_group = None
    num_rounds = 1
    invalid_f_char = 'invalid_string'


class Subsession(BaseSubsession):
    pass


class Group(BaseGroup):
    pass


class Player(BasePlayer):
    f_bool = models.BooleanField()
    f_posint = models.IntegerField(min=2)
    f_float = models.FloatField()
    f_currency = models.CurrencyField()
    f_char = models.CharField()

    timeout_happened = models.BooleanField(initial=False)
