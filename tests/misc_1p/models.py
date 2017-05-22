# -*- coding: utf-8 -*-
# <standard imports>
from __future__ import division
from otree.api import (
    models, BaseConstants, BaseSubsession, BaseGroup, BasePlayer,
    Currency as c, widgets
)
# </standard imports>


doc = """
Test misc functionality of a 1-player game
"""


class Constants(BaseConstants):
    name_in_url = 'misc_1p'
    players_per_group = None
    num_rounds = 1


class Subsession(BaseSubsession):

    def creating_session(self):
        self.session.vars['a'] = 1
        if self.round_number == 1:
            for p in self.get_players():
                p.participant.vars['a'] = 1
            for g in self.get_groups():
                for p2 in g.get_players():
                    p2.participant.vars['b'] = 1
        for p3 in self.get_players():
            p3.in_creating_session = 1
        for g2 in self.get_groups():
            g2.in_creating_session = 1


class Group(BaseGroup):
    def set_payoffs(self):
        for p in self.get_players():
            p.payoff = c(50)

    # example field
    min_max = models.CurrencyField(
        doc="""
        Description of this field, for documentation
        """,
        min=5,
        max=10
    )

    dynamic_min_max = models.CurrencyField()

    in_creating_session = models.CurrencyField()


class Player(BasePlayer):

    def other_player(self):
        """Returns other player in group. Only valid for 2-player groups."""
        return self.get_others_in_group()[0]

    blank = models.CharField(blank=True)

    add100_1 = models.PositiveIntegerField()
    add100_2 = models.PositiveIntegerField()

    even_int = models.PositiveIntegerField()

    after_next_button_field = models.BooleanField()

    dynamic_choices = models.CharField()

    radio = models.CurrencyField(
        widget=widgets.RadioSelect(),
        choices=[c(1), c(2)]
    )

    dynamic_radio = models.CharField(widget=widgets.RadioSelectHorizontal())

    dynamic_min_max = models.CurrencyField()

    in_creating_session = models.CurrencyField()

    def role(self):
        # you can make this depend of self.id_in_group
        return ''
