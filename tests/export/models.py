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
    num_rounds = 2


class Subsession(BaseSubsession):
    subsession_field = models.CharField(initial='should be in export CSV')
    align = models.CharField()
    align_session = models.CharField()

    def before_session_starts(self):
        self.group_randomly()
        self.align = 'SUBSESSION_{}'.format(self.id)
        self.align_session = 'ALIGN_TO_SESSION_{}'.format(self.session.code)
        for g in self.get_groups():
            g.align = 'GROUP_{}'.format(g.id)
            g.align_subsession = 'ALIGN_TO_SUBSESSION_{}'.format(self.id)
        for p in self.get_players():
            p.align_group = 'ALIGN_TO_GROUP_{}'.format(p.group.id)
            p.align_participant = 'ALIGN_TO_PARTICIPANT_{}'.format(p.participant.code)

class Group(BaseGroup):
    group_field = models.BooleanField(initial=False)
    align = models.CharField()
    align_subsession = models.CharField()


class Player(BasePlayer):
    player_field = models.CurrencyField(initial=Currency(3.14))
    align_group = models.CharField()
    align_participant = models.CharField()
