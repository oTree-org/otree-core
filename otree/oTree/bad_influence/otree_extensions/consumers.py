import networkx as nx
from networkx.readwrite import json_graph
from channels.generic.websocket import AsyncJsonWebsocketConsumer, JsonWebsocketConsumer
import time
import json
from asgiref.sync import async_to_sync
from bad_influence.models import Player, Group, Constants, Message
import random


class NetworkVoting(AsyncJsonWebsocketConsumer):

    def clean_kwargs(self):
        self.player_pk = self.scope['url_route']['kwargs']['player_pk']
        self.group_pk = self.scope['url_route']['kwargs']['group_pk']

    async def connect(self):
        self.clean_kwargs()
        # Join
        await self.channel_layer.group_add(
            self.connection_groups(),
            self.channel_name
        )

        await self.accept()
        print("Connected to Network Socket")

    async def disconnect(self, close_code):
        self.clean_kwargs()
        await self.channel_layer.group_discard(
            self.connection_groups(),
            self.channel_name
        )
        print("Disconnected from Network Socket")

    def connection_groups(self, **kwargs):
        group_name = self.get_group().get_channel_group_name()
        personal_channel = self.get_player().get_personal_channel_name()
        return "{}-{}".format(group_name, personal_channel)

    def get_player(self):
        return Player.objects.get(pk=self.player_pk)

    def get_group(self):
        return Group.objects.get(pk=self.group_pk)

    async def receive(self, text_data):
        self.clean_kwargs()
        text_data_json = json.loads(text_data)
        msg = text_data_json['message']
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
                channel_cur = "{}-{}".format(self.get_group().get_channel_group_name(), p.get_personal_channel_name())

                await self.channel_layer.group_send(
                    channel_cur,
                    {
                        "type": "send_choice",
                        "message": {
                            "ego_graph": ego_graph,
                            "consensus": consensus
                        }
                    }
                )
            print("Player received message.")

    async def send_choice(self, event):
        message = event['message']

        # Send message to WebSocket
        await self.send(text_data=json.dumps({
            'message': message
        }))

        print("Sent message")


class ChatConsumer(AsyncJsonWebsocketConsumer):
    def new_message(self, data):
        player = data['from']
        player_user = Player.objects.filter(id=player)[0]
        message = Message.objects.create(
            player=player_user,
            content=data['message']
        )
        content = {
            'command': 'new_message',
            'message': self.message_to_json(message)
        }
        return self.send_chat_message(content)

    def fetch_messages(self, data):
        messages = Message.last_ten_messages()
        content = {
            'command': 'fetch_message',
            'messages': self.messages_to_json(messages)
        }
        self.send_message(content)

    @staticmethod
    def message_to_json(message):
        return {
            'player': message.player_id,
            'content': message.content,
            'timestamp': str(message.timestamp),
        }

    def messages_to_json(self, messages):
        result = []
        for message in messages:
            result.append(self.message_to_json(message))
        return result

    commands = {
        'new_message': new_message,
        'fetch_messages': fetch_messages
    }

    def connect(self):
        # self.player_pk = self.scope['url_route']['kwargs']['player_pk']
        self.group_pk = self.scope['url_route']['kwargs']['group_pk']
        self.room_name = 'chat_%s' % self.group_pk
        print("Player connected onto Chat Socket in group {}".format(self.group_pk))
        print(Player.hex_color(self))

        # Join room group
        async_to_sync(self.channel_layer.group_add)(
            self.room_name,
            self.channel_name
        )

        self.accept()

    def disconnect(self, close_code):
        # Leave room group
        async_to_sync(self.channel_layer.group_discard)(
            self.room_name,
            self.channel_name
        )
        print('Disconnect from socket')

    def get_group(self):
        return Group.objects.get(pk=self.group_pk)

    # Receive message from WebSocket
    def receive(self, text_data):
        data = json.loads(text_data)
        self.commands[data['command']](self, data)

    def send_chat_message(self, message):
        async_to_sync(self.channel_layer.group_send)(
            self.room_name, {
                'type': 'chat_message',
                'message': message
            }
        )

    def send_message(self, message):
        self.send(text_data=json.dumps(message))

    def chat_message(self, event):
        message = event['message']
        self.send(text_data=json.dumps(message))
