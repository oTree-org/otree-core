# -*- coding: utf-8 -*-
# <standard imports>
from __future__ import division
from otree.api import (
    BaseSubsession, BaseGroup, BasePlayer, BaseConstants, models
)
# </standard imports>

doc = ""

class Constants(BaseConstants):
    name_in_url = 'group_by_arrival_time'
    players_per_group = 2
    num_rounds = 3


class Subsession(BaseSubsession):
    pass


class Group(BaseGroup):
    set_in_wait_page = models.BooleanField(default=False)


class Player(BasePlayer):
    set_in_wait_page = models.BooleanField(default=False)
