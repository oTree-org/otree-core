# -*- coding: utf-8 -*-
# <standard imports>
from __future__ import division
from otree.api import (
    BaseSubsession, BaseGroup, BasePlayer, BaseConstants, models,
    Currency
)

# </standard imports>

doc = "foo"


class Constants(BaseConstants):
    name_in_url = 'data_export'
    players_per_group = None
    num_rounds = 1


class Subsession(BaseSubsession):
    subsession_field = models.CharField(initial='should be in export CSV')


class Group(BaseGroup):
    group_field = models.BooleanField(initial=False)


class Player(BasePlayer):
    player_field = models.CurrencyField(initial=Currency(3.14))
