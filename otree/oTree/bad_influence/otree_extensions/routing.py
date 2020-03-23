from channels.routing import route_class
from .consumers import NetworkVoting

channel_routing = [
    route_class(NetworkVoting, path=NetworkVoting.url_pattern),
]