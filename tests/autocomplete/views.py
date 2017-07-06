from otree.api import Currency as c, currency_range
from . import models
from ._builtin import Page, WaitPage
from .models import Constants


class Wait1(WaitPage):
    # should autocomplete
    group_by_arrival_time = True

    def is_displayed(self):
        # player could be underlined in yellow,
        # because usually we don't use self.player in WaitPages
        # but could change in the future

        # return self.player.id_in_group == 1
        pass

    def get_players_for_group(self, waiting_players):
        pass


class Page1(Page):
    def vars_for_template(self):
        return {
            # should autocomplete
            'a': self.player.f_bool,
            'b': self.participant.vars.items(),
            'c': self.player.participant.session.config,
            'd': self.session.config,
        }

    # should autocomplete
    def get_timeout_seconds(self): pass

    def before_next_page(self):
        # should autocomplete
        _ = self.timeout_happened

page_sequence = [Wait1, Page1]
