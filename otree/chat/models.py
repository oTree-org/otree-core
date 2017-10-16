from django.db import models
from otree.models import Participant
import time
import re
from otree.api import safe_json
from django.core.signing import Signer
import otree.channels.utils as channel_utils

class ChatMessage(models.Model):
    class Meta:
        index_together = ['channel', 'timestamp']

    # the name "channel" here is unrelated to Django channels
    channel = models.CharField(max_length=255)
    participant = models.ForeignKey(Participant)
    nickname = models.CharField(max_length=255)

    # call it 'body' instead of 'message' or 'content' because those terms
    # are already used by channels
    body = models.TextField()
    timestamp = models.FloatField(default=time.time)


class ChatTagError(Exception):
    pass


# template tag
def chat_template_tag(context, *args, **kwargs):
    player = context['player']
    group = context['group']
    Constants = context['Constants']
    participant = context['participant']

    kwargs.setdefault('channel', group.id)
    kwargs.setdefault('nickname', 'Player {}'.format(player.id_in_group))

    nickname = str(kwargs['nickname'])
    unprefixed_channel = str(kwargs['channel'])

    # channel name should not contain illegal chars,
    # so that it can be used in JS and URLs
    if not re.match(r'^[a-zA-Z0-9_-]+$', unprefixed_channel):
        raise ChatTagError(
            "'channel' can only contain ASCII letters, numbers, underscores, and hyphens. "
            "Value given was: {}".format(unprefixed_channel))

    # prefix the channel name with session code and app name
    channel = '{}-{}-{}-{}'.format(
        context['session'].id,
        # name_in_url could be very long, so take the first chars
        # and combine with a hash to ensure uniqueness
        Constants.name_in_url[:50],
        hash(Constants.name_in_url),
        kwargs['channel']
    )

    context['channel'] = channel

    nickname_signed = Signer().sign(nickname)

    socket_path = channel_utils.chat_path(channel, participant.id)

    vars_for_js = {
        'socket_path': socket_path,
        'channel': channel,
        'participant_id': participant.id,
        'nickname_signed': nickname_signed,
    }

    context['vars_for_js'] = safe_json(vars_for_js)

    return context

