from . import consumers
from django.conf.urls import re_path

# channel_routing = [
#     route_class(NetworkVoting, path=NetworkVoting.url_pattern),
# ]n

websocket_routes = [
            re_path(r'ws/network_voting/(?P<group_pk>[0-9]+)/(?P<player_pk>[0-9]+)$', consumers.NetworkVoting),
            re_path(r'ws/chat/(?P<player_pk>[0-9]+)/(?P<group_pk>[0-9]+)$', consumers.ChatConsumer)
        ]
