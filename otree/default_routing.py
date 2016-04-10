from channels.routing import route, include

from otree import consumers


channel_routing = [
    route(
        'websocket.connect',
         consumers.connect_wait_page,
        path=r'^/wait_page/$'),
    route(
        'websocket.disconnect',
             consumers.connect_wait_page,
        path=r'^/wait_page/$'),
    route(
        'websocket.connect',
         consumers.connect_auto_advance,
        path=r'^/auto_advance/(?P<participant_code>[a-z]+)/$'),
    route(
        'websocket.disconnect',
             consumers.disconnect_auto_advance,
        path=r'^/auto_advance/(?P<participant_code>[a-z]+)/$'),
]
