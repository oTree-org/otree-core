from django.core.signing import Signer
from asgiref.sync import async_to_sync
from channels.layers import get_channel_layer
from urllib.parse import urlencode

_group_send = get_channel_layer().group_send
_sync_group_send = async_to_sync(_group_send)


def sync_group_send_wrapper(*, type: str, group: str, event: dict):
    '''make it a function that takes proper args that are intuitive.
    enforces correct use.
    '''
    return _sync_group_send(group, {'type': type, **event})


def group_send_wrapper(*, type: str, group: str, event: dict):
    '''make it a function that takes proper args that are intuitive.
    '''
    return _group_send(group, {'type': type, **event})


def group_wait_page_name(session_id, page_index, group_id):

    return 'wait-page-{}-page{}-{}'.format(
        session_id, page_index, group_id
    )


def subsession_wait_page_name(session_id, page_index):

    return 'wait-page-{}-page{}'.format(session_id, page_index)


def gbat_group_name(session_id, page_index):
    return 'group_by_arrival_time_session{}_page{}'.format(session_id, page_index)


def gbat_path(**kwargs):
    return '/group_by_arrival_time/?' + urlencode(kwargs)


def room_participants_group_name(room_name):
    return 'room-participants-{}'.format(room_name)


def room_participant_path(**kwargs):
    return '/wait_for_session_in_room/?' + urlencode(kwargs)


def session_monitor_group_name(session_code):
    return f'session-monitor-{session_code}'

def session_monitor_path(session_code):
    return f'/session_monitor/{session_code}/'


def room_admin_group_name(room_name):
    return f'room-admin-{room_name}'


def room_admin_path(room_name):
    return '/room_without_session/{}/'.format(room_name)


def create_session_path():
    return '/create_session/'


def create_demo_session_path():
    return '/create_demo_session/'


def group_wait_page_path(**kwargs):
    return '/wait_page/?' + urlencode(kwargs)


def subsession_wait_page_path(**kwargs):
    return '/subsession_wait_page/?' + urlencode(kwargs)


def browser_bots_launcher_group(session_code):
    return 'browser-bots-client-{}'.format(session_code)


def browser_bots_launcher_path(session_code):
    return '/browser_bots_client/{}/'.format(session_code)


def auto_advance_path(**kwargs):
    return '/auto_advance/?' + urlencode(kwargs)


def auto_advance_group(participant_code):
    return f'auto-advance-{participant_code}'


def live_group(session_code, page_index):
    '''
    live_method_hash is so that you can send messages across pages that share the same
    live_method. But you don't want to send messages to a different live_method page.
    '''
    return f'live-{session_code}-{page_index}'


def live_path(**kwargs):
    return f'/live/?' + urlencode(kwargs)


def chat_path(channel, participant_id):
    channel_and_id = '{}/{}'.format(channel, participant_id)
    channel_and_id_signed = Signer(sep='/').sign(channel_and_id)

    return '/otreechat_core/{}/'.format(channel_and_id_signed)


def get_chat_group(channel):
    return 'otreechat-{}'.format(channel)
