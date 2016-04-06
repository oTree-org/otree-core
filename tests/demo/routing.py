from channels.routing import route
from .chat import consumers as chat_consumers


channel_routing = [
    route(
        'websocket.connect',
        chat_consumers.connect_chat,
        path=r'^/chat/$'),
    route(
        'websocket.receive',
        chat_consumers.handle_message,
        path=r'^/chat/$'),
    route(
        'websocket.disconnect',
        chat_consumers.disconnect_chat,
        path=r'^/chat/$'),
]
