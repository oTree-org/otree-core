from otree.api import (
    BaseSubsession, BaseGroup, BasePlayer, BaseConstants, models,
    Currency as c
)

doc = '''
THIS GAME DOES NOT ACTUALLY RUN, and should not be included in session config.
It's just to testing that autocomplete works properly when editing these source
files in PyCharm.
'''

class Constants(BaseConstants):
    name_in_url = 'autocomplete'
    players_per_group = None
    num_rounds = 2


class Subsession(BaseSubsession):

    # should auto-complete if I start typing the method name
    def vars_for_admin_report(self):
        pass

    def before_session_starts(self):
        for g in self.get_group_matrix():
            for p in g:
                # autocomplete
                _ = p.id_in_group

                # no yellow
                _ = p.f_bool

class Group(BaseGroup):
    f_posint = models.PositiveIntegerField()

    def foo(self):
        # method should autocomplete
        x = self.get_player_by_id(1)

        # .id_in_group should autocomplete
        _ = x.id_in_group

        # no yellow highlight
        _ = x.f_currency
        x.f()

        for p in self.get_players():
            _ = p.id_in_group


class Player(BasePlayer):
    f_currency = models.CurrencyField(choices=[1,2])
    f_int = models.IntegerField(
        blank=False, # should be auto-completed
        db_index=True # should NOT be auto-completed
    )
    f_bool = models.BooleanField()
    f_char = models.CharField()

    def no_yellow_errors(self):
        '''None of these should be highlighted in yellow'''
        _ = self.f_currency + 1
        _ = self.f_currency + c(1)
        _ = c(1) + 1
        _ = c(1) / c(1)
        _ = self.f_int + 1
        _ = self.f_int + c(1)
        _ = self.f_bool + 1
        _ = self.group.f_posint

    def foo(self):
        # each of these should autocomplete
        self.participant.vars.clear()
        _ = self.session.config

        for p in self.in_all_rounds():
            # autocomplete
            _ = p.id_in_group

            # no yellow
            _ = p.f_bool


    def f(self): pass