from ._builtin import Page, WaitPage
import networkx as nx
from networkx.readwrite import json_graph
import json
from .models import Constants
from .questions import make_question
import time
import numpy as np


class MyNormalWaitPage(WaitPage):
    template_name = 'bad_influence/MyResultsWaitPage.html'
    title_text = "Vent..."
    def after_all_players_arrive(self):
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
        print(self.group.get_graph())
        graph = json_graph.node_link_data(
            nx.ego_graph(self.group.get_graph(), self.player.id_in_group))

        return {
                'network': json.dumps(graph),
                'consensus': int(self.group.get_consensus() * 100),
                'question': make_question(self.group, self.player.hub, self.player.gender, self.player.number_of_friends)
               }

    def before_next_page(self):
        self.group.round_end_time = time.time()


class MyResultsWaitPage(WaitPage):
    template_name = 'bad_influence/MyResultsWaitPage.html'
    title_text = "Vent..."
    def after_all_players_arrive(self):
        for player in self.group.get_players():
            player.set_payoffs()
            player.get_question_title()
        self.group.stubborness()

    def vars_for_template(self):
        return {'payoff': int(self.participant.payoff)}


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

        return {
            "data": json.dumps(data),
            "payoff": int(self.participant.payoff),
            'player_in_all_rounds': self.player.in_all_rounds(),
            'get_others_in_group': self.player.get_others_in_group(),
            'fraction_hub': str(np.sum([p.hub for p in self.player.in_all_rounds()]))+'/'+str(Constants.num_rounds),
            'total_friends': np.sum([p.number_of_friends for p in self.player.in_all_rounds()]),
            'total_opinion_changes': np.sum([p.opinion_change for p in self.player.in_all_rounds()]),
            'total_stubborn': np.around(np.sum([p.stubborn for p in self.player.in_all_rounds()]),1),
            "id_in_group": self.player.id_in_group
        }


page_sequence = [
    MyNormalWaitPage,
    Play,
    MyResultsWaitPage,
    Results,
]
