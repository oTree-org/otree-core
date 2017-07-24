from otree.api import (
    BaseSubsession, BaseGroup, BasePlayer, BaseConstants, models
)

doc = ""

class Constants(BaseConstants):
    name_in_url = 'constants'
    players_per_group = None
    num_rounds = 1
    c_str = 'a'
    c_int = 1
    c_list = [1,2]


class Subsession(BaseSubsession):
    pass


class Group(BaseGroup):
    pass


class Player(BasePlayer):
    pass