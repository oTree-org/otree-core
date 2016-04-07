from channels.routing import route
from .chat import consumers as chat_consumers


channel_routing = [
    route(
        'websocket.connect',
        chat_consumers.connect_wait_page,
        path=r'^/wait_page/(?P<group_name>[a-zA-Z0-9_-]+)$'),
    route(
        'websocket.disconnect',
        chat_consumers.disconnect_wait_page,
        path=r'^/wait_page/(?P<group_name>[a-zA-Z0-9_-]+)$'),
]
