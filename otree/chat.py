import re
from django.core.signing import Signer
from otree.channels import utils as channel_utils
from django.utils.translation import ugettext as _

class ChatTagError(Exception):
    pass


def chat_template_tag(context, *args, **kwargs):
    player = context['player']
    group = context['group']
    Constants = context['Constants']
    participant = context['participant']


    unprefixed_channel = str(kwargs.pop('channel', group.id))
    # Translators: A player's default chat nickname,
    # which is "Player" + their ID in group. For example:
    # "Player 2".
    default_chat_nickname = _('Player {id_in_group}').format(id_in_group=player.id_in_group)
    nickname = str(kwargs.pop('nickname', default_chat_nickname))

    for kwarg in kwargs:
        raise ChatTagError(
            # need double {{ to escape because of .format()
            '{{% chat %}} tag received unrecognized parameter "{}"'.format(kwarg)
        )

    # channel name should not contain illegal chars,
    # so that it can be used in JS and URLs
    if not re.match(r'^[a-zA-Z0-9_-]+$', unprefixed_channel):
        raise ChatTagError(
            "'channel' can only contain ASCII letters, numbers, underscores, and hyphens. "
            "Value given was: {}".format(unprefixed_channel))

    # prefix the channel name with session code and app name
    channel = '{}-{}-{}'.format(
        context['session'].id,
        Constants.name_in_url,
        # previously used a hash() here to ensure name_in_url is the same,
        # but hash() is non-reproducible across processes
        unprefixed_channel
    )

    context['channel'] = channel

    nickname_signed = Signer().sign(nickname)

    socket_path = channel_utils.chat_path(channel, participant.id)

    vars_for_js = {
        'socket_path': socket_path,
        'channel': channel,
        'participant_id': participant.id,
        'nickname_signed': nickname_signed,
        # Translators: the name someone sees displayed for themselves in a chat.
        # It's their nickname followed by "(Me)". For example:
        # "Michael (Me)" or "Player 1 (Me)".
        'nickname_i_see_for_myself': _("{nickname} (Me)").format(nickname=nickname)
    }

    context['vars_for_js'] = vars_for_js

    return context