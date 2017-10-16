from channels.routing import route, route_class
from otree.chat.consumers import ChatConsumer

# NOTE: otree_extensions is part of
# otree-core's private API, which may change at any time.
channel_routing = [
    route_class(
        ChatConsumer,
        path=r"^/otreechat/(?P<params>[a-zA-Z0-9_/-]+)/$"),
    #route('otree.chat_messages', msg_consumer),
]
