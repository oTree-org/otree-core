# -*- coding: utf-8 -*-
# <standard imports>
from __future__ import division
from otree.api import (
    BaseSubsession, BaseGroup, BasePlayer, BaseConstants, models
)
# </standard imports>

doc = "foo"

class Constants(BaseConstants):
    name_in_url = 'admin_report'
    players_per_group = None
    num_rounds = 2


class Subsession(BaseSubsession):
    foo = models.PositiveIntegerField(initial=42)

    def vars_for_admin_report(self):
        return {'custom_var': 43}


class Group(BaseGroup):
    pass


class Player(BasePlayer):
    pass
