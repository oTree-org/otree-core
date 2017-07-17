from __future__ import division
from otree.api import (
    BaseSubsession, BaseGroup, BasePlayer, BaseConstants, models
)
import itertools

doc = "Testing get_players_for_group()"

class Constants(BaseConstants):
    name_in_url = 'group_by_arrival_time_custom'
    players_per_group = None
    num_rounds = 2


class Subsession(BaseSubsession):
    def before_session_starts(self):
        types = itertools.cycle(['A','B'])
        for p in self.get_players():
            p.type = next(types)


class Group(BaseGroup):
    pass


class Player(BasePlayer):
    type = models.CharField()
