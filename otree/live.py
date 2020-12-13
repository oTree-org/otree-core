import otree.common
import otree.db
from otree.channels import utils as channel_utils
from otree.models import Participant
from otree.lookup import get_page_lookup
import logging
from otree.db import idmap


logger = logging.getLogger(__name__)


def live_payload_function(participant_code, page_name, payload):

    participant = Participant.objects.get(code=participant_code)
    lookup = get_page_lookup(participant._session_code, participant._index_in_pages)
    app_name = lookup.app_name
    models_module = otree.common.get_models_module(app_name)
    PageClass = lookup.page_class
    # this could be incorrect if the player advances right after liveSend is executed.
    # maybe just return if it doesn't match. (but leave it in for now and see how much that occurs,
    # don't want silent failures.)
    if page_name != PageClass.__name__:
        logger.warning(
            f'Ignoring liveSend message from {participant_code} because '
            f'they are on page {PageClass.__name__}, not {page_name}.'
        )
        return
    live_method_name = PageClass.live_method

    with idmap.use_cache():
        player = models_module.Player.objects.get(
            round_number=lookup.round_number, participant=participant
        )

        # it makes sense to check the group first because
        # if the player forgot to define it on the Player,
        # we shouldn't fall back to checking the group. you could get an error like
        # 'Group' has no attribute 'live_auction' which would be confusing.
        # also, we need this 'group' object anyway.
        # and this is a good place to show the deprecation warning.
        group = player.group
        if hasattr(group, live_method_name):
            method = getattr(group, live_method_name)
            retval = method(player.id_in_group, payload)
        else:
            method = getattr(player, live_method_name)
            retval = method(payload)

    if not retval:
        return
    if not isinstance(retval, dict):
        msg = f'{live_method_name} must return a dict'
        raise LiveMethodBadReturnValue(msg)

    pcodes_dict = {
        d['id_in_group']: d['participant__code']
        for d in models_module.Player.objects.filter(group=group).values(
            'participant__code', 'id_in_group'
        )
    }

    if 0 in retval:
        if len(retval) > 1:
            raise LiveMethodBadReturnValue(
                'If dict returned by live_method has key 0, it must not contain any other keys'
            )
    else:
        for pid in retval:
            if pid not in pcodes_dict:
                msg = f'live_method has invalid return value. No player with id_in_group={repr(pid)}'
                raise LiveMethodBadReturnValue(msg)

    pcode_retval = {}
    for pid, pcode in pcodes_dict.items():
        payload = retval.get(pid, retval.get(0))
        if payload is not None:
            pcode_retval[pcode] = payload

    _live_send_back(
        participant._session_code, participant._index_in_pages, pcode_retval
    )


class LiveMethodBadReturnValue(Exception):
    pass


def _live_send_back(session_code, page_index, pcode_retval):
    '''separate function for easier patching'''
    group_name = channel_utils.live_group(session_code, page_index)
    channel_utils.sync_group_send_wrapper(
        group=group_name, type='send_back_to_client', event=pcode_retval
    )
