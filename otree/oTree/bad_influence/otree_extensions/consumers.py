import networkx as nx
from networkx.readwrite import json_graph
from channels.generic.websockets import JsonWebsocketConsumer
from bad_influence.models import Player, Group, Constants
import time


class NetworkVoting(JsonWebsocketConsumer):
    url_pattern = r'^/network_voting/(?P<player_pk>[0-9]+)/(?P<group_pk>[0-9]+)$'

    def clean_kwargs(self):
        self.player_pk = self.kwargs['player_pk']
        self.group_pk = self.kwargs['group_pk']

    def connect(self, message, **kwargs):
        self.clean_kwargs()
        print('connection from {}:{}'.format(self.group_pk, self.player_pk))

    def disconnect(self, message, **kwargs):
        self.clean_kwargs()
        print('disconnect from {}:{}'.format(self.group_pk, self.player_pk))

    def connection_groups(self, **kwargs):
        group_name = self.get_group().get_channel_group_name()
        personal_channel = self.get_player().get_personal_channel_name()
        return [group_name, personal_channel]

    def get_player(self):
        self.clean_kwargs()
        return Player.objects.get(pk=self.player_pk)

    def get_group(self):
        self.clean_kwargs()
        return Group.objects.get(pk=self.group_pk)

    def receive(self, text=None, bytes=None, **kwargs):
        self.clean_kwargs()
        msg = text
        player = self.get_player()
        group = self.get_group()

        if msg['action'] == 'guess' and msg['payload'] != player.choice:
            new_guess = msg['payload']
            timestamp = time.time()

            subjective_time = msg['subjective_time'].split(":")
            if len(subjective_time) == 1:
                subjective_time = int(subjective_time[0]) * 60
            else:
                subjective_time = int(subjective_time[0]) * 60 + int(subjective_time[1])

            player.choice = new_guess
            player.last_choice_made_at = Constants.round_length - subjective_time
            player.save()

            graph = group.get_graph()
            consensus = group.get_consensus()

            group.add_to_history({
                "nodes": json_graph.node_link_data(graph)['nodes'],
                "minority_ratio": group.get_minority_ratio(),
                "time": timestamp,
                "choice": {
                    "id": player.id_in_group,
                    "value": player.choice,
                    "subjective_time": player.last_choice_made_at
                }
            })

            for p in group.get_players():
                ego_graph = json_graph.node_link_data(nx.ego_graph(graph, p.id_in_group))
                self.group_send(p.get_personal_channel_name(), {
                    'ego_graph': ego_graph,
                    'consensus': consensus
                })
