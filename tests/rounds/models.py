# -*- coding: utf-8 -*-
# <standard imports>
from __future__ import division
from otree.api import (
    BaseSubsession, BaseGroup, BasePlayer, BaseConstants, models
)
# </standard imports>

doc = "foo"

class Constants(BaseConstants):
    name_in_url = 'rounds'
    players_per_group = 2
    num_rounds = 3


class Subsession(BaseSubsession):
    pass


class Group(BaseGroup):
    pass


class Player(BasePlayer):
    pass
