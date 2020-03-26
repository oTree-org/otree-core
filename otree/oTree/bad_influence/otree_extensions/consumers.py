import networkx as nx
from networkx.readwrite import json_graph
from channels.generic.websocket import AsyncWebsocketConsumer, JsonWebsocketConsumer, WebsocketConsumer
from bad_influence.models import Player, Group, Constants
import time
import json
from asgiref.sync import async_to_sync


class NetworkVoting(JsonWebsocketConsumer):
    # url_pattern = r'^/network_voting/(?P<player_pk>[0-9]+)/(?P<group_pk>[0-9]+)$'

    def clean_kwargs(self, **kwargs):
        self.player_pk = kwargs['player_pk']
        self.group_pk = kwargs['group_pk']

    def connect(self):
        self.player_pk = self.scope['url_route']['kwargs']['player_pk']
        self.group_pk = self.scope['url_route']['kwargs']['group_pk']

        # Join
        self.channel_layer.group_add(
            self.player_pk,
            self.group_pk
        )

    def disconnect(self, close_code):
        self.clean_kwargs()
        print('disconnect from {}:{}'.format(self.group_pk, self.player_pk))
        async_to_sync(self.channel_layer.group_discard)(
            self.connection_groups()
        )

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

    def receive(self, text):
        self.clean_kwargs()
        text_json = json.loads(text)
        message = text_json['message']
        player = self.get_player()
        group = self.get_group()

        if message['action'] == 'guess' and message['payload'] != player.choice:
            new_guess = message['payload']
            timestamp = time.time()

            subjective_time = message['subjective_time'].split(":")
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
                async_to_sync(self.channel_layer.group_send)(
                    "chat",
                    {
                        "type": "chat.message",
                        "text": text
                    },
                    p.get_personal_channel_name(),
                    {
                        "ego_graph": ego_graph,
                        "consensus": consensus
                    }
                )


class ChatConsumer(AsyncWebsocketConsumer):
    async def connect(self):
        self.player_pk = self.scope['url_route']['kwargs']['player_pk']
        self.group_pk = self.scope['url_route']['kwargs']['group_pk']
        self.room_name = "{}-{}".format(self.player_pk, self.group_pk)

        # Join room group
        await self.channel_layer.group_add(
            self.room_name,
            self.channel_name
        )

        await self.accept()

    async def disconnect(self, close_code):
        # Leave room group
        await self.channel_layer.group_discard(
            self.room_name,
            self.channel_name
        )

    # Receive message from websocket
    async def receive(self, text_data):
        text_data_json = json.loads(text_data)
        message = text_data_json['message']

        # Send message to room group
        await self.channel_layer.group_send(
            self.room_name,
            {
                "type": "chat_message",
                "message": message,
                "player_pk": self.player_pk
            }
        )


class ChatroomConsumer(WebsocketConsumer):
    def connect(self):
        self.accept()

    def disconnect(self, close_code):
        pass

    def receive(self, text_data):
        text_data_json = json.loads(text_data)
        message = text_data_json['message']

        self.send(text_data=json.dumps({
            'message': message
        }))
