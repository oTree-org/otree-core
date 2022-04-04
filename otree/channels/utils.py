from otree.common import signer_sign
import asyncio
from collections import defaultdict
from typing import DefaultDict, Dict
from urllib.parse import urlencode
import websockets.exceptions
from starlette.websockets import WebSocket

from otree.common import signer_sign
from otree.currency import json_dumps


def wrap_websocket_send(original_send):
    async def send(message):
        try:
            await original_send(message)
        except websockets.exceptions.ConnectionClosed:
            # "You can catch and handle ConnectionClosed to prevent it from being logged."
            # https://websockets.readthedocs.io/en/latest/howto/faq.html#what-does-connectionclosederror-no-close-frame-received-or-sent-mean
            pass

    return send


class ChannelLayer:
    _subs: DefaultDict[str, Dict[int, WebSocket]]

    def _get_sockets(self, group):
        for socket in self._subs[group].values():
            yield socket

    def __init__(self):
        self._subs = defaultdict(dict)

    def add(self, group: str, websocket: WebSocket):
        self._subs[group][id(websocket)] = websocket

    def discard(self, group, websocket):
        group_dict = self._subs[group]
        group_dict.pop(id(websocket), None)
        # prune it so this global var doesn't grow indefinitely
        if not group_dict:
            del self._subs[group]

    async def send(self, group, data):
        for socket in self._get_sockets(group):
            await socket.send_text(json_dumps(data))

    def sync_send(self, group, data):
        asyncio.run(self.send(group, data))


channel_layer = ChannelLayer()


async def group_send(*, group: str, data: dict):
    await channel_layer.send(group, data)


def sync_group_send(*, group: str, data: dict):
    channel_layer.sync_send(group=group, data=data)


def group_wait_page_name(session_id, page_index, group_id):

    return 'wait-page-{}-page{}-{}'.format(session_id, page_index, group_id)


def subsession_wait_page_name(session_id, page_index):

    return 'wait-page-{}-page{}'.format(session_id, page_index)


def gbat_group_name(session_id, page_index):
    return 'group_by_arrival_time_session{}_page{}'.format(session_id, page_index)


def gbat_path(**kwargs):
    return '/group_by_arrival_time?' + urlencode(kwargs)


def room_participants_group_name(room_name):
    return 'room-participants-{}'.format(room_name)


def room_participant_path(**kwargs):
    return '/wait_for_session_in_room?' + urlencode(kwargs)


def session_monitor_group_name(session_code):
    return f'session-monitor-{session_code}'


def session_monitor_path(session_code):
    return f'/session_monitor/{session_code}'


def room_admin_group_name(room_name):
    return f'room-admin-{room_name}'


def room_admin_path(room_name):
    return '/room_without_session/{}'.format(room_name)


def create_session_path():
    return '/create_session'


def create_demo_session_path():
    return '/create_demo_session'


def group_wait_page_path(**kwargs):
    return '/wait_page?' + urlencode(kwargs)


def subsession_wait_page_path(**kwargs):
    return '/subsession_wait_page?' + urlencode(kwargs)


def browser_bots_launcher_group(session_code):
    return 'browser-bots-client-{}'.format(session_code)


def browser_bots_launcher_path(session_code):
    return '/browser_bots_client/{}'.format(session_code)


def auto_advance_path(**kwargs):
    return '/auto_advance?' + urlencode(kwargs)


def auto_advance_group(participant_code):
    return f'auto-advance-{participant_code}'


def live_group(session_code, page_index, pcode):
    '''
    live_method_hash is so that you can send messages across pages that share the same
    live_method. But you don't want to send messages to a different live_method page.
    '''
    return f'live-{session_code}-{page_index}-{pcode}'


def live_path(**kwargs):
    return f'/live?' + urlencode(kwargs)


def chat_path(channel, participant_id):
    return '/chat?' + urlencode(
        {
            'channel': signer_sign(channel),
            'participant_id': signer_sign(str(participant_id)),
        }
    )


def get_chat_group(channel):
    return 'otreechat-{}'.format(channel)
