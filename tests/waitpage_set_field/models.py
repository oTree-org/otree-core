# -*- coding: utf-8 -*-
# <standard imports>
from __future__ import division
from otree.api import (
    BaseSubsession, BaseGroup, BasePlayer, BaseConstants, models
)
# </standard imports>

doc = ""

class Constants(BaseConstants):
    name_in_url = 'waitpage_set_field'
    players_per_group = 4
    num_rounds = 50


class Subsession(BaseSubsession):
    pass


class Group(BaseGroup):
    pass


class Player(BasePlayer):
    set_to_false = models.BooleanField(initial=True)
