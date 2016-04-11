from channels.routing import route, include

from otree import consumers


channel_routing = [
    route(
        'websocket.connect',
        consumers.connect_wait_page,
        path=r'^/wait_page/(?P<params>[\w,]+)/$'),
    route(
        'websocket.disconnect',
        consumers.disconnect_wait_page,
        path=r'^/wait_page/(?P<params>[\w,]+)/$'),
    route(
        'websocket.connect',
         consumers.connect_auto_advance,
        path=r'^/auto_advance/(?P<params>[\w,]+)/$'),
    route(
        'websocket.disconnect',
             consumers.disconnect_auto_advance,
        path=r'^/auto_advance/(?P<params>[\w,]+)/$'),
]
