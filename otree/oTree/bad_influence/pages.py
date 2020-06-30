from django.contrib.auth import authenticate, login
from django.contrib.auth.forms import UserCreationForm
from django.template import response
from ._builtin import Page, WaitPage
import networkx as nx
from networkx.readwrite import json_graph
import json
from .models import Constants, Message
from .questions import make_question
import time
import numpy as np


class Intro1(Page):
    timeout_seconds = Constants.round_length
    def is_displayed(self):
        return self.round_number == 1


class Intro2(Page):
    timeout_seconds = Constants.round_length
    def is_displayed(self):
        return self.round_number == 1


class Intro3(Page):
    timeout_seconds = Constants.round_length
    form_model = 'player'
    form_fields = ['navn']
    def is_displayed(self):
        return self.round_number == 1


class MyNormalWaitPage(WaitPage):
    template_name = 'bad_influence/MyResultsWaitPage.html'
    title_text = "Vent..."

    def after_all_players_arrive(self):
        for player in self.group.get_players():
            player.set_names()
        group = self.group
        group.round_start_time = time.time()
        group.add_to_history({
            "nodes": json_graph.node_link_data(group.get_graph())['nodes'],
            "minority_ratio": group.get_minority_ratio(),
            "time": group.round_start_time,
            "choice": "start_of_round"
        })

    def vars_for_template(self):
        return {'payoff': int(self.participant.payoff)}


class Play(Page):
    timeout_seconds = Constants.round_length
    form_model = 'player'

    def vars_for_template(self):
        graph = json_graph.node_link_data(
            nx.ego_graph(self.group.get_graph(), self.player.id_in_group))
        return {
            'network': json.dumps(graph),
            'consensus': int(self.group.get_consensus() * 100),
            'question': make_question(self.group, self.player.hub, self.player.gender, self.player.number_of_friends),
        }

    def before_next_page(self):
        self.group.round_end_time = time.time()

    def new_message(self):
        new_message = Message.objects.create()
        return new_message


class MyResultsWaitPage(WaitPage):
    template_name = 'bad_influence/MyResultsWaitPage.html'
    title_text = "Vent..."

    def after_all_players_arrive(self):
        for player in self.group.get_players():
            player.set_points()
            player.get_question_title()
            player.get_choice_text()
            player.get_preference_text()
        self.group.stubborness()

    def vars_for_template(self):
        return {'payoff': int(self.participant.payoff)}


class PartResults(Page):
    timeout_seconds = 10
    def is_displayed(self):
        return self.round_number < Constants.num_rounds

    def vars_for_template(self):
        # data = [{
        #     "graph": json_graph.node_link_data(group.get_graph()),
        #     "history": json.loads(group.history),
        #     "question": make_question(group, self.player.hub, self.player.gender, self.player.number_of_friends),
        #     "start_time": group.round_start_time,
        #     "end_time": group.round_end_time,
        # } for group in self.group.in_all_rounds()]

        rankings = []
        for p in self.subsession.get_players():
            #p.stubborn_total = sum([player.stubborn for player in p.in_all_rounds()])
            #p.opinion_change_total = sum([player.opinion_change for player in p.in_all_rounds()])
            #p.number_of_friends_total = sum([player.number_of_friends for player in p.in_all_rounds()])
            p.points_total = sum([player.points for player in p.in_all_rounds()])
            # p.fulgt_flertallet_pct = 100 * sum(
            #     [1 for player in p.in_all_rounds() if player.points != 0]) / Constants.num_rounds
            # p.fulgt_preference_pct = 100 * sum(
            #     [1 for player in p.in_all_rounds() if player.hub == player.choice]) / Constants.num_rounds
            # rankings.append((p.id_in_group, p.points_total, p.fulgt_flertallet_pct,
            #                  p.fulgt_preference_pct, np.around(p.stubborn_total, 1),
            #                  p.number_of_friends_total, p.opinion_change_total))
            rankings.append((p.id_in_group, p.points_total))
        sorted_rankings = sorted(rankings, key=lambda x: x[1], reverse=True)
        for idx, rank in enumerate(sorted_rankings):
            if rank[0] == self.player.id_in_group:
                placering = idx + 1

        return {
        #     "data": json.dumps(data),
            "payoff_ialt": np.sum([p.points for p in self.player.in_all_rounds()]),
        #     'player_in_all_rounds': self.player.in_all_rounds(),
        #     'get_others_in_group': self.player.get_others_in_group(),
        #     'fraction_hub': str(np.sum([p.hub for p in self.player.in_all_rounds()])) + '/' + str(Constants.num_rounds),
        #     'total_friends': np.sum([p.number_of_friends for p in self.player.in_all_rounds()]),
        #     'total_opinion_changes': np.sum([p.opinion_change for p in self.player.in_all_rounds()]),
        #     'total_stubborn': np.around(np.sum([p.stubborn for p in self.player.in_all_rounds()]), 1),
        #     "id_in_group": self.player.id_in_group,
            "rankings": placering, #sorted(rankings, key=lambda x: x[1], reverse=True),
        #     "json_rank": json.dumps(rankings)
        }


class Results(Page):
    def is_displayed(self):
        return self.round_number >= Constants.num_rounds

    def vars_for_template(self):
        data = [{
            "graph": json_graph.node_link_data(group.get_graph()),
            "history": json.loads(group.history),
            "question": make_question(group, self.player.hub, self.player.gender, self.player.number_of_friends),
            "start_time": group.round_start_time,
            "end_time": group.round_end_time,
        } for group in self.group.in_all_rounds()]

        rankings = []
        for p in self.subsession.get_players():
            p.stubborn_total = sum([player.stubborn for player in p.in_all_rounds()])
            p.opinion_change_total = sum([player.opinion_change for player in p.in_all_rounds()])
            p.number_of_friends_total = sum([player.number_of_friends for player in p.in_all_rounds()])
            p.points_total = sum([player.points for player in p.in_all_rounds()])
            p.fulgt_flertallet_pct = 100 * sum(
                [1 for player in p.in_all_rounds() if player.points != 0]) / Constants.num_rounds
            p.fulgt_preference_pct = 100 * sum(
                [1 for player in p.in_all_rounds() if player.hub == player.choice]) / Constants.num_rounds
            rankings.append((p.id_in_group, p.points_total, p.fulgt_flertallet_pct,
                             p.fulgt_preference_pct, np.around(p.stubborn_total, 1),
                             p.number_of_friends_total, p.opinion_change_total))

        return {
            "data": json.dumps(data),
            "payoff_ialt": np.sum([p.points for p in self.player.in_all_rounds()]),
            'player_in_all_rounds': self.player.in_all_rounds(),
            'get_others_in_group': self.player.get_others_in_group(),
            'fraction_hub': str(np.sum([p.hub for p in self.player.in_all_rounds()])) + '/' + str(Constants.num_rounds),
            'total_friends': np.sum([p.number_of_friends for p in self.player.in_all_rounds()]),
            'total_opinion_changes': np.sum([p.opinion_change for p in self.player.in_all_rounds()]),
            'total_stubborn': np.around(np.sum([p.stubborn for p in self.player.in_all_rounds()]), 1),
            "id_in_group": self.player.id_in_group,
            "rankings": sorted(rankings, key=lambda x: x[1], reverse=True),
            "json_rank": json.dumps(rankings)
        }


class Outro1(Page):
    timeout_seconds = Constants.round_length
    def is_displayed(self):
        return self.round_number == Constants.num_rounds


class Outro2(Page):
    timeout_seconds = Constants.round_length
    def is_displayed(self):
        return self.round_number == Constants.num_rounds


page_sequence = [
    Intro1,
    Intro2,
    Intro3,
    MyNormalWaitPage,
    Play,
    MyResultsWaitPage,
    PartResults,
    Results,
    Outro1,
    Outro2,
]
