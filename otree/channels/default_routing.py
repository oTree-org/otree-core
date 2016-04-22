from channels.routing import route

from otree.channels import consumers

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
    route('websocket.connect',
          consumers.connect_wait_for_session,
          path=r'^/wait_for_session/(?P<pre_create_id>\w+)/$'),
    route('websocket.disconnect',
          consumers.disconnect_wait_for_session,
          path=r'^/wait_for_session/(?P<pre_create_id>\w+)/$'),
    route('otree.create_session',
          consumers.create_session)
]
