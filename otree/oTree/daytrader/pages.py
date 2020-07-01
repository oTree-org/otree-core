from otree.api import Currency as c, currency_range
from . import models
from ._builtin import Page, WaitPage
from .models import Constants, Player


class Intro1(Page):
    timeout_seconds = Constants.timeout90

    def is_displayed(self):
        return self.round_number == 1


class Intro2(Page):
    timeout_seconds = Constants.timeout90

    def is_displayed(self):
        return self.round_number == 1


class Intro3(Page):
    timeout_seconds = Constants.timeout90

    def is_displayed(self):
        return self.round_number == 1


class Intro4(Page):
    timeout_seconds = Constants.timeout90

    def is_displayed(self):
        return self.round_number == 1


class Intro4b(Page):
    timeout_seconds = Constants.timeout90

    def is_displayed(self):
        return self.round_number == 1


class Intro5(Page):
    timeout_seconds = Constants.timeout90

    def is_displayed(self):
        return self.round_number == 1


class Intro6(Page):
    timeout_seconds = Constants.timeout90

    def is_displayed(self):
        return self.round_number == 1


class MyWaitPage(WaitPage):
    title_text = "Vent til alle er klar"
    body_text = "Spillet starter om et øjeblik..."

    def after_all_players_arrive(self):
        for player in self.group.get_players():
            player.new_share_price()
            player.update_wallet()
            player.choice_of_number_of_shares_max()


class Choose(Page):
    form_model = 'player'  # setting a form model for current player
    form_fields = ['choice_of_trade', 'choice_of_number_of_shares']  # setting a form field to fill out

    timeout_seconds = Constants.timeout30

    # retrieving variables for a trade history table
    def vars_for_template(self):
        prices = [self.session.vars['{}{}'.format(self.player.company_name, r)][0]
                  for r in range(1, self.player.round_number)]
        choices = [self.session.vars['{}{}'.format(self.player.company_name, r)][3]
                   for r in range(1, self.round_number)]
        deals = [self.session.vars['{}{}'.format(self.player.company_name, r)][4]
                 for r in range(1, self.player.round_number)]
        rounds = [r for r in range(1, self.player.round_number)]
        states = []
        for player in Player.objects.all():
            states.append(player.drawn_face)

        data = zip(rounds, prices, choices, deals, states)
        game_rounds = Constants.num_rounds
        current_round = self.player.round_number

        return {
            'data': data,
            'rounds': rounds,
            'runder': game_rounds,
            'current_round': current_round
        }


class ResultsWaitPage(WaitPage):
    def after_all_players_arrive(self):
        for player in self.group.get_players():
            player.save_in_session_vars()


class Delisted(Page):
    def is_displayed(self):
        return self.player.price < 1

    def vars_for_template(self):
        return {
            'max_minus': -Constants.max_borrow
        }


class Results(Page):
    def is_displayed(self):
        return self.round_number == Constants.num_rounds

    def vars_for_template(self):
        tjent = self.player.payoff()
        firma = [p.company_name for p in self.player.in_all_rounds()]
        tilstand = [p.company_state for p in self.player.in_all_rounds()]
        choices = [p.choice_of_trade for p in self.player.in_all_rounds()]
        handler = [p.choice_of_number_of_shares for p in self.player.in_all_rounds()]
        price = [c(p.price) for p in self.player.in_all_rounds()]
        closing = [c(p.closing_price(p.company_name)) for p in self.player.in_all_rounds()]
        data = zip(firma, tilstand, choices, handler, price, closing, tjent)
        handelsvaerdi = c(sum([p.price * p.choice_of_number_of_shares
                               for p in self.player.in_all_rounds()]))

        rankings = []
        if 'profit' in self.session.vars:
            for p in self.group.get_players():
                rankings.append((p.id_in_group, p.tjent_ialt))
        else:
            for p in self.group.get_players():
                rankings.append((p.id_in_group, 0))

        return {
            'handlet': handelsvaerdi,
            'kurtage_pct': int(Constants.kurtage * 100),
            'kurtage': c(Constants.kurtage * handelsvaerdi),
            'ialt': self.player.tjent_ialt - (Constants.kurtage * handelsvaerdi),
            'data': data,
            'firma': firma,
            'tilstand': tilstand,
            'choices': choices,
            'handler': handler,
            'price': price,
            'closing': closing,
            'tjent': tjent,
            'rankings': sorted(rankings, key=lambda x: x[1], reverse=True),
        }


page_sequence = [
    Intro1,
    Intro2,
    Intro3,
    Intro4,
    Intro4b,
    Intro5,
    Intro6,
    MyWaitPage,
    Choose,
    ResultsWaitPage,
    Delisted,
    Results
]
