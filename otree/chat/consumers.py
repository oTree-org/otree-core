# In consumers.py
from channels import Group, Channel
from .models import ChatMessage
import json
from otree.channels.consumers import (
    OTreeJsonWebsocketConsumer, InvalidWebSocketParams)
from django.core.signing import Signer, BadSignature

def get_chat_group(channel):
    return 'otreechat-{}'.format(channel)


class ChatConsumer(OTreeJsonWebsocketConsumer):

    # Set to True if you want it, else leave it out
    strict_ordering = False

    def clean_kwargs(self, params):

        signer = Signer(sep='/')
        try:
            original_params = signer.unsign(params)
        except BadSignature:
            raise InvalidWebSocketParams

        channel, participant_id = original_params.split('/')

        return {
            'channel': channel,
            'participant_id': int(participant_id),
        }

    def group_name(self, channel, participant_id):
        return get_chat_group(channel)

    def post_connect(self, **kwargs):

        history = ChatMessage.objects.filter(
            channel=kwargs['channel']).order_by('timestamp').values(
                'nickname', 'body', 'participant_id'
        )

        # Convert ValuesQuerySet to list
        self.send(list(history))

    def post_receive(self, content, channel, participant_id):
        content['channel'] = channel
        content['participant_id'] = participant_id

        # in the Channels docs, the example has a separate msg_consumer
        # channel, so this can be done asynchronously.
        # but i think the perf is probably good enough.
        # moving into here for simplicity, especially for testing.
        nickname_signed = content['nickname_signed']
        nickname = Signer().unsign(nickname_signed)
        channel = content['channel']
        channels_group = get_chat_group(channel)

        body = content['body']
        participant_id = content['participant_id']

        chat_message = {
            'nickname': nickname,
            'body': body,
            'participant_id': participant_id
        }

        Group(channels_group).send({'text': json.dumps([chat_message])})

        ChatMessage.objects.create(
            participant_id=participant_id,
            channel=channel,
            body=body,
            nickname=nickname
        )
