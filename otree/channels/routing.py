from channels.auth import AuthMiddlewareStack
from channels.routing import ProtocolTypeRouter, URLRouter
from django.conf.urls import url
from otree.channels import consumers
from otree.extensions import get_extensions_modules

websocket_routes = [
    # WebSockets
    url(r'^wait_page/$', consumers.GroupWaitPage),
    url(r'^subsession_wait_page/$', consumers.SubsessionWaitPage),
    url(r'^group_by_arrival_time/$', consumers.GroupByArrivalTime),
    url(r'^auto_advance/$', consumers.DetectAutoAdvance),
    url(r'^create_session/$', consumers.CreateSession),
    url(r'^create_demo_session/$', consumers.CreateDemoSession),
    url(r'^delete_sessions/$', consumers.DeleteSessions),
    url(r'^wait_for_session_in_room/$', consumers.RoomParticipant),
    url(r'^room_without_session/(?P<room>\w+)/$', consumers.RoomAdmin),
    url(r'^session_monitor/(?P<code>\w+)/$', consumers.SessionMonitor),
    url(r'^browser_bots_client/(?P<session_code>\w+)/$', consumers.BrowserBotsLauncher),
    url(r'^browser_bot_wait/$', consumers.BrowserBot),
    url(
        # so it doesn't clash with addon
        r"^live/$",
        consumers.LiveConsumer,
    ),
    url(
        # so it doesn't clash with addon
        r"^otreechat_core/(?P<params>[a-zA-Z0-9_/-]+)/$",
        consumers.ChatConsumer,
    ),
    url(r"^export/$", consumers.ExportData),
    url(r'^no_op/$', consumers.NoOp),
]


extensions_modules = get_extensions_modules('routing')
for extensions_module in extensions_modules:
    websocket_routes += getattr(extensions_module, 'websocket_routes', [])


application = ProtocolTypeRouter(
    {
        "websocket": AuthMiddlewareStack(URLRouter(websocket_routes)),
        "lifespan": consumers.LifespanApp,
    }
)
