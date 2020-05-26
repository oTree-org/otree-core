from otree.api import (
    models, widgets, BaseConstants, BaseSubsession, BaseGroup, BasePlayer,
    Currency as c, currency_range
)
from django.conf import settings
import random
import json
import pandas as pd
import matplotlib

matplotlib.use('Agg')
import matplotlib.pyplot as plt
import numpy as np
from cycler import cycler

names = pd.read_excel("daytrader/Fictional_Company_Names.xlsx")
author = 'Robin Engelhardt'
doc = """
In this experiment a firm is represented by a bag, containing a
variable number of 'happy' and 'sad' faces. Players have to pull
out one face and guess the overall state of the firm, e.g. whether it is
in a mainly 'happy' or mainly 'sad' condition. Informational cascades will
form, but since the bag (in a secondary treatment) can change
its state with a fixed probability, a mix of strategies need to be employed.
"""


# random.seed(8)


class Constants(BaseConstants):
    name_in_url = 'daytrader'
    players_per_group = None
    num_rounds = 5
    timeouts = 60

    # share attributes
    num_shares = 100000
    start_price = 50.0
    start_wallet = 10000
    price_change_per_share = 0.001
    kurtage = 0.01

    # firm attributes
    num_faces = 3


class Json_action:
    @staticmethod
    def from_string(bag):
        return json.loads(bag)

    @staticmethod
    def to_string(bag):
        return json.dumps(bag)


class Subsession(BaseSubsession):
    def creating_session(self):
        # creating static company names and states in round 1, save in session.vars
        # and retrieve for next rounds. Else we get an assignment error.
        if self.round_number == 1:
            number_of_players = self.session.num_participants
            # number_of_players = self.session.config['num_demo_participants']
            company_names = random.sample(names["Name"].tolist(), number_of_players)
            company_states = [[bool(random.getrandbits(1))
                               for _ in range(Constants.num_faces)]
                              for _ in range(number_of_players)]
            self.session.vars['number_of_players'] = number_of_players
            self.session.vars['company_names'] = company_names
            self.session.vars['company_states'] = company_states

            # for i in range(len(company_names)):
            #     print(i, company_names[i], company_states[i])
            # print(self.session.vars)
        else:
            number_of_players = self.session.vars['number_of_players']
            company_names = self.session.vars['company_names']
            company_states = self.session.vars['company_states']

        for idp, player in enumerate(self.get_players()):
            if self.round_number == 1:
                player.wallet = Constants.start_wallet
                player.price = Constants.start_price
            player.company_name = company_names[(idp + self.round_number - 1) % number_of_players]
            player.company_state = Json_action.to_string(
                company_states[(idp + self.round_number - 1) % number_of_players])
            player.drawn_face = random.choice(Json_action.from_string(player.company_state))
            # player.number_of_glad_faces = sum(Json_action.from_string(player.company_state))

    def vars_for_admin_report(self):
        graph_colors = [
            [0.996, 0.875, 0.431, 1],  # Yellow
            [0.302, 0.82, 0.208, 1],   # Green
            [0.416, 0.953, 0.984, 1],  # Turkish
            [0.686, 0.686, 0.686, 1],  # Grey
            [0.984, 0.729, 0.816, 1],  # Pink
            [0.98, 0.251, 0.329, 1],   # Red
        ]
        plt.rc('axes', prop_cycle=(cycler(color=graph_colors)))
        fig = plt.figure(figsize=(4, 3))
        ax = plt.axes()
        for company_name in self.session.vars['company_names']:
            # find the number of rounds played by looking in the dict and store
            # in tmp0:
            tmp0 = sum([1
                        if '{}{}'.format(company_name, r) in self.session.vars
                        else 0
                        for r in range(1, Constants.num_rounds + 2)])
            prices = [self.session.vars['{}{}'.format(company_name, r)][0]
                      for r in range(1, tmp0)]
            x = np.linspace(1, len(prices), len(prices))
            ax.plot(x, prices, marker='o', label=company_name)
        ax.legend(loc='upper left', bbox_to_anchor=(1.04, 1))
        ax.set_xlabel('runde', fontdict={'fontsize': 12})
        ax.set_ylabel('pris', fontdict={'fontsize': 12})
        ax.set_title('Aktieprisudvikling', fontsize='x-large')
        fig.savefig('_static/daytrader/test.pdf', transparent=True,
                    bbox_inches='tight', dpi=300)
        fig.savefig('_static/daytrader/test.png', transparent=True,
                    bbox_inches='tight', dpi=300)

        names = self.session.vars['company_names']
        states = self.session.vars['company_states']
        choices = [[self.session.vars['{}{}'.format(name, r)][3]
                    for r in range(1, tmp0)] for name in names]
        drawn_faces = [[self.session.vars['{}{}'.format(name, r)][2]
                    for r in range(1, tmp0)] for name in names]
        round_list = [r for r in range(1, tmp0 + 1)]

        return dict(company=list(zip(names, states, choices, drawn_faces)), round_list=round_list, faces=drawn_faces)


class Group(BaseGroup):
    pass


class Player(BasePlayer):
    wallet = models.CurrencyField()
    company_name = models.StringField()
    company_state = models.StringField()
    # number_of_glad_faces = models.PositiveIntegerField()
    drawn_face = models.BooleanField()
    choice_of_trade = models.IntegerField(
        choices=[
            [1, 'køb (long)'],
            [0, 'lån og sælg (short)'],
        ],
        widget=widgets.RadioSelectHorizontal()
    )
    price = models.CurrencyField()
    price_change = models.CurrencyField()
    choice_of_number_of_shares = models.PositiveIntegerField(default=0, max=1000)
    can_buy = models.PositiveIntegerField()

    def choice_of_number_of_shares_max(self):
        if self.wallet <= 0.0:
            return 0
        num_shares_that_can_be_bought = int(self.wallet / self.price)
        self.can_buy = min([num_shares_that_can_be_bought, 1000])
        return self.can_buy

    def old_share_price(self):
        if self.round_number > 1:
            tmp = '{}{}'.format(self.company_name, self.round_number - 1)
            return self.session.vars[tmp][0]
        else:
            return Constants.start_price

    # def old_choice(self):
    #     if self.round_number == 1:
    #         return 2
    #     else:
    #         tmp = '{}{}'.format(self.company_name, self.round_number-1)
    #         return self.session.vars[tmp][3]

    def old_num_shares(self):
        if self.round_number == 1:
            return 0
        else:
            tmp = '{}{}'.format(self.company_name, self.round_number - 1)
            return self.session.vars[tmp][4]

    def new_share_price(self):
        if self.round_number == 1:
            self.price = Constants.start_price
        else:
            price_change = 0.0

            # retrieve actions from previous round:
            tmp = '{}{}'.format(self.company_name, self.round_number - 1)
            previous_choice_of_trade = self.session.vars[tmp][3]
            previous_choice_of_number_of_shares = self.session.vars[tmp][4]

            # calculate price change and add up
            if previous_choice_of_trade == 1:
                price_change += Constants.price_change_per_share * previous_choice_of_number_of_shares
            else:
                price_change -= Constants.price_change_per_share * previous_choice_of_number_of_shares
            self.price = self.old_share_price() + price_change * self.old_share_price()
        return self.price

    def update_wallet(self):
        if self.round_number == 1:
            self.wallet = Constants.start_wallet
        else:
            # retrieve actions from previous round:
            previous_price = self.in_round(self.round_number - 1).price
            previous_choice_of_number_of_shares = self.in_round(self.round_number - 1).choice_of_number_of_shares
            self.wallet = self.in_round(
                self.round_number - 1).wallet - previous_price * previous_choice_of_number_of_shares
        return self.wallet

    def save_in_session_vars(self):
        tmp = '{}{}'.format(self.company_name, self.round_number)
        self.session.vars[tmp] = (self.price,
                                  self.id_in_group,
                                  self.drawn_face,
                                  self.choice_of_trade,
                                  self.choice_of_number_of_shares)
        if self.round_number == Constants.num_rounds:
            tmp1 = '{}{}'.format(self.company_name, Constants.num_rounds + 1)
            self.session.vars[tmp1] = self.closing_price(self.company_name)

    def closing_price(self, company):
        # retrieve actions from last trade:
        tmp = '{}{}'.format(company, Constants.num_rounds)
        tmp0 = self.session.vars[tmp][0]
        tmp3 = self.session.vars[tmp][3]
        tmp4 = self.session.vars[tmp][4]

        price_change = 0.0
        if tmp3 == 1:
            price_change += Constants.price_change_per_share * tmp4
        elif tmp3 == 0:
            price_change -= Constants.price_change_per_share * tmp4
        else:
            price_change += 0

        return tmp0 + price_change * tmp0

    def payoff(self):
        # the earnings are calculated after last round and stored in
        # in participant.vars and summed in self.payoff
        self.participant.vars['profit'] = []
        for idp, p in enumerate(self.in_all_rounds()):
            if p.choice_of_trade == 1:
                self.participant.vars['profit'].append((self.closing_price(p.company_name)
                                                        - p.price) * p.choice_of_number_of_shares)
            else:
                self.participant.vars['profit'].append(-(self.closing_price(p.company_name)
                                                         - p.price) * p.choice_of_number_of_shares)
        self.payoff = sum(self.participant.vars['profit'])
        return self.participant.vars['profit']
