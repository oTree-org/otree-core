from channels.routing import route, route_class

from otree.channels import consumers
from otree.extensions import get_extensions_modules
from channels.routing import route, route_class


channel_routing = [

    route('otree.create_session',
          consumers.create_session),

    # WebSockets
    route_class(
        consumers.WaitPage,
        path=r'^/wait_page/(?P<params>[\w,]+)/$'),
    route_class(
        consumers.GroupByArrivalTime,
        path=r'^/group_by_arrival_time/(?P<params>[\w,\.]+)/$'),
    route_class(
        consumers.AutoAdvance,
        path=r'^/auto_advance/(?P<params>[\w,]+)/$'),
    route_class(consumers.WaitForSession,
          path=r'^/wait_for_session/(?P<pre_create_id>\w+)/$'),
    route_class(
          consumers.RoomParticipant,
          path=r'^/wait_for_session_in_room/(?P<params>[\w,]+)/$'),
    route_class(
          consumers.RoomAdmin,
          path=r'^/room_without_session/(?P<room>\w+)/$'),
    route_class(
          consumers.BrowserBotsLauncher,
          path=r'^/browser_bots_client/(?P<session_code>\w+)/$'),
    route_class(
          consumers.BrowserBot,
          path=r'^/browser_bot_wait/$'),
    route_class(
        consumers.ChatConsumer,
        # so it doesn't clash with addon
        path=r"^/otreechat_core/(?P<params>[a-zA-Z0-9_/-]+)/$"),
    route_class(
        consumers.ExportData,
        # need authentication! like add admin_secret_code.
        path=r"^/export/$"),

]

# TODO: perf issue. this takes 0.1-0.5 seconds.
for extensions_module in get_extensions_modules('routing'):
    channel_routing += getattr(extensions_module, 'channel_routing', [])
