# -*- coding: utf-8 -*-
# <standard imports>
from __future__ import division
from otree.api import (
    BaseSubsession, BaseGroup, BasePlayer, BaseConstants, models
)
# </standard imports>

doc = "foo"

class Constants(BaseConstants):
    name_in_url = 'waitpage_template'
    players_per_group = None
    num_rounds = 1
    wait_page_template = 'waitpage_template/CustomWaitPage.html'
    custom_title_text = 'custom_title_text'
    custom_body_text = 'custom_body_text'


class Subsession(BaseSubsession):
    pass


class Group(BaseGroup):
    pass


class Player(BasePlayer):
    pass
