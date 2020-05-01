from . import consumers
from django.conf.urls import re_path

websocket_routes = [
    re_path(r'ws/chat/(?P<group_pk>[0-9]+)$', consumers.ChatConsumer),
    re_path(r'ws/network_voting/(?P<player_pk>[0-9]+)/(?P<group_pk>[0-9]+)$', consumers.NetworkVoting),
]
