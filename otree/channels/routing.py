from otree.channels import consumers
from otree.extensions import get_extensions_modules

from django.conf.urls import url

from channels.routing import ProtocolTypeRouter, URLRouter, ChannelNameRouter
from channels.auth import AuthMiddlewareStack


websocket_routes = [
    # WebSockets
    url(r'^wait_page/$', consumers.GroupWaitPage),
    url(r'^subsession_wait_page/$', consumers.SubsessionWaitPage),
    url(r'^group_by_arrival_time/$', consumers.GroupByArrivalTime),
    url(r'^auto_advance/$', consumers.DetectAutoAdvance),
    url(r'^create_session/$', consumers.CreateSession),
    url(r'^create_demo_session/$', consumers.CreateDemoSession),
    url(r'^wait_for_session_in_room/$', consumers.RoomParticipant),
    url(r'^room_without_session/(?P<room>\w+)/$', consumers.RoomAdmin),
    url(r'^browser_bots_client/(?P<session_code>\w+)/$', consumers.BrowserBotsLauncher),
    url(r'^browser_bot_wait/$', consumers.BrowserBot),
    url(
        # so it doesn't clash with addon
        r"^otreechat_core/(?P<params>[a-zA-Z0-9_/-]+)/$",
        consumers.ChatConsumer,
    ),
    url(r"^export/$", consumers.ExportData),
    # for django autoreloader
    # just so client can detect when server has finished restarting
    url(r'^no_op/$', consumers.NoOp),
]


extensions_modules = get_extensions_modules('routing')
for extensions_module in extensions_modules:
    websocket_routes += getattr(extensions_module, 'websocket_routes', [])


application = ProtocolTypeRouter(
    {"websocket": AuthMiddlewareStack(URLRouter(websocket_routes))}
)
