import networkx as nx
from networkx.readwrite import json_graph
from channels.generic.websocket import AsyncJsonWebsocketConsumer, WebsocketConsumer
import time
import json
from bad_influence.models import Player, Group, Constants, Message, Subsession
import datetime
from asgiref.sync import async_to_sync


class NetworkVoting(AsyncJsonWebsocketConsumer):
    # Cleans the kwargs needed for the socket's route argument
    # In routing.py a regex look for player_pk and group_pk
    # The arguments are passed from the model in the page.py
    # to the play.html page and via the websocket routing name
    # in JavaScript passed to the Consumer
    def clean_kwargs(self):
        self.player_pk = self.scope['url_route']['kwargs']['player_pk']
        self.group_pk = self.scope['url_route']['kwargs']['group_pk']

    # Channels connect function connect to the WebSocket
    async def connect(self):
        # runs the clean_kwargs so they can be used in the channel
        self.clean_kwargs()

        # Adds the group name to a group
        await self.channel_layer.group_add(
            self.connection_groups(),
            self.channel_name
        )

        # Accepts an incoming socket
        await self.accept()

    # Function called when the Socket disconnects / the socket's connection is closed.
    async def disconnect(self, close_code):
        self.clean_kwargs()

        # Removes the group from the channel
        await self.channel_layer.group_discard(
            self.connection_groups(),
            self.channel_name
        )

    # Defines the group name for the channel
    def connection_groups(self, **kwargs):
        group_name = self.get_group().get_channel_group_name()
        personal_channel = self.get_player().get_personal_channel_name()
        return "{}-{}".format(group_name, personal_channel)

    # Gets the player's primary key
    def get_player(self):
        return Player.objects.get(pk=self.player_pk)

    # Gets the group's primary key
    def get_group(self):
        return Group.objects.get(pk=self.group_pk)

    # Call the websocket_receive function which is called when a WebSocket frame is received,
    # decodes it and calls receive()
    async def receive(self, text_data):
        self.clean_kwargs()

        # Takes the received text_data and converts it into json
        text_data_json = json.loads(text_data)
        # The received message from the JSON data
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

                # Defines a specific channel for each specific network, which is used as the channels group name
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

    async def send_choice(self, event):
        message = event['message']

        # Sends the message to WebSocket
        await self.send(text_data=json.dumps({
            'message': message
        }))


class ChatConsumer(WebsocketConsumer):
    # Fetches messages from the database
    def fetch_messages(self, data):
        # Fetches all the messages from the database
        all_messages = Message.objects.all()
        # If there exist more than 0 messages in database do following:
        if len(all_messages) > 0:
            # Loop through the messages
            for message in all_messages:
                # if each message in the database's group id is not equal to the data's group id delete the messages
                # which group id is not equal to the data's group id
                if message.group_id != data['group_id']:
                    Message.objects.get(pk=message.id).delete()

        # Get the last 15 messages from the database
        messages = Message.last_15_messages()
        # Issues the command 'messages' for fetching the last 15 messages and turns them into JSON
        content = {
            'command': 'messages',
            'messages': self.messages_to_json(messages)
        }

        # Send the content
        self.send_message(content)

    # Creates a new message and saves it to the database
    def new_message(self, data):
        # Creates a new message
        message = Message.objects.create(
             content=data['message'],
             timestamp=datetime.datetime.now(),
             player_id=data['player_id'],
             chat_id=data['chat_id'],
             group_id=data['group_id']
        )

        # Issues the command 'new_message' for creating a new message and turns the new message to JSON
        content = {
            'message': self.message_to_json(message),
            'command': 'new_message'
        }

        # Sends the chat message with chat message in JSON
        return self.send_chat_message(content)

    # Turns multiple message into JSON
    def messages_to_json(self, messages):
        # List for the messages
        result = []
        # Loops through the received messages data
        for message in messages:
            # Uses the message_to_json function to append each message to the result list
            result.append(self.message_to_json(message))
        return result

    # Turns a single message into JSON
    def message_to_json(self, message):
        # Returns the received message's data
        return {
            'player_id': message.player_id,
            'chat_id': message.chat_id,
            'content': message.content,
            'timestamp': str(message.timestamp),
            'group_id': message.group_id
        }

    # Command controller
    commands = {
        'fetch_messages': fetch_messages,
        'new_message': new_message
    }

    # Channels connect function connect to the WebSocket
    def connect(self):
        # Defines the arguments used for the channel's group name
        self.group_pk = self.scope['url_route']['kwargs']['group_pk']
        self.room_name = 'chat_%s' % self.group_pk

        # Adds the group name to a group
        async_to_sync(self.channel_layer.group_add)(
            self.room_name,
            self.channel_name
        )

        # Accepts an incoming socket
        self.accept()

    # Function called when the Socket disconnects / the socket's connection is closed.
    def disconnect(self, close_code):
        # Removes the group from the channel
        async_to_sync(self.channel_layer.group_discard)(
            self.room_name,
            self.channel_name
        )

    # Call the websocket_receive function which is called when a WebSocket frame is received,
    # decodes it and calls receive()
    # The receive function in the ChatConsumer calls the specific command which in turn calls the associated function,
    # the data is then received and passed on
    def receive(self, text_data):
        data = json.loads(text_data)
        self.commands[data['command']](self, data)

    # Send a chat message to client
    def send_chat_message(self, message):
        # Send a chat message to each channel
        async_to_sync(self.channel_layer.group_send)(
            self.room_name,
            {
                'type': 'chat_message',
                'message': message
            }
        )

    # Converts the message into JSON and sends it
    def send_message(self, message):
        self.send(text_data=json.dumps(message))

    # Takes the received event's message and turns into JSON and sends it
    # This function is then in turn called in the send_chat_message function, when a chat message is send to
    # each channel
    def chat_message(self, event):
        message = event['message']
        self.send(text_data=json.dumps(message))
