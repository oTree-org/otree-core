from channels.routing import route, route_class
from otree.chat.consumers import ChatConsumer

# NOTE: otree_extensions is part of
# otree-core's private API, which may change at any time.
channel_routing = [
    route_class(
        ChatConsumer,
        # so it doesn't clash with addon
        path=r"^/otreechat_core/(?P<params>[a-zA-Z0-9_/-]+)/$"),
    #route('otree.chat_messages', msg_consumer),
]
