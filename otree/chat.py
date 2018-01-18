import re
from django.core.signing import Signer
from otree.channels import utils as channel_utils


class ChatTagError(Exception):
    pass


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

    context['vars_for_js'] = vars_for_js

    return context