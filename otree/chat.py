import re
from otree.common import signer_sign, signer_unsign

from otree.channels import utils as channel_utils
from gettext import gettext


class ChatTagError(Exception):
    pass


class UNDEFINED:
    pass


def chat_template_tag(context, *, channel=UNDEFINED, nickname=UNDEFINED) -> dict:
    player = context['player']
    group = context['group']
    Constants = context['Constants']
    participant = context['participant']

    if channel == UNDEFINED:
        channel = group.id
    channel = str(channel)
    # channel name should not contain illegal chars,
    # so that it can be used in JS and URLs
    if not re.match(r'^[a-zA-Z0-9_-]+$', channel):
        msg = (
            "'channel' can only contain ASCII letters, numbers, underscores, and hyphens. "
            "Value given was: {}".format(channel)
        )
        raise ChatTagError(msg)
    # prefix the channel name with session code and app name
    prefixed_channel = '{}-{}-{}'.format(
        context['session'].id,
        Constants.name_in_url,
        # previously used a hash() here to ensure name_in_url is the same,
        # but hash() is non-reproducible across processes
        channel,
    )
    context['channel'] = prefixed_channel

    if nickname == UNDEFINED:
        # Translators: A player's default chat nickname,
        # which is "Player" + their ID in group. For example:
        # "Player 2".
        nickname = gettext('Participant {id_in_group}').format(
            id_in_group=player.id_in_group
        )
    nickname = str(nickname)
    nickname_signed = signer_sign(nickname)

    socket_path = channel_utils.chat_path(prefixed_channel, participant.id)

    chat_vars_for_js = dict(
        channel=prefixed_channel,
        socket_path=socket_path,
        participant_id=participant.id,
        nickname_signed=nickname_signed,
        nickname=nickname,
        nickname_i_see_for_myself=gettext("{nickname} (Me)").format(nickname=nickname),
    )
    return dict(
        channel=prefixed_channel,
        # send this as one item so it can be json dumped & loaded into js
        # in one line.
        chat_vars_for_js=chat_vars_for_js,
    )
