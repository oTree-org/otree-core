from channels.routing import route, include

from otree import consumers

channel_routing = [
    route(
        'websocket.connect',
        consumers.connect_wait_page,
        name='connect_wait_page',

        #path=r'^/wait_page/(?P<group_name>[a-zA-Z0-9_-]+)$'),
        path=r'^/abcd/$'),
    route(
        'websocket.disconnect',
        consumers.disconnect_wait_page,
        name='disconnect_wait_page',
        #path=r'^/wait_page/(?P<group_name>[a-zA-Z0-9_-]+)$'),
        path=r'^/abcd/$'),
]

