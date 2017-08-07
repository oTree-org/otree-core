from otree.api import (
    models, BaseConstants, BaseSubsession, BaseGroup, BasePlayer,
    Currency as c, widgets
)


doc = """
Test general functionality:
-   Framework methods like creating_session, before_next_page, etc are executed
-   Modifications to objects are saved
"""


class Constants(BaseConstants):
    name_in_url = 'saving'
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

    in_creating_session = models.CurrencyField()


class Player(BasePlayer):

    after_next_button_field = models.BooleanField()
    in_creating_session = models.CurrencyField()
