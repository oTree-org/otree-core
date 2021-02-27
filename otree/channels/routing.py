from starlette.routing import WebSocketRoute as WSR
from . import consumers as cs

websocket_routes = [
    WSR('/wait_page', cs.WSGroupWaitPage),
    WSR('/subsession_wait_page', cs.WSSubsessionWaitPage),
    WSR('/group_by_arrival_time', cs.WSGroupByArrivalTime),
    WSR('/auto_advance', cs.DetectAutoAdvance),
    WSR('/create_session', cs.WSCreateSession),
    WSR('/create_demo_session', cs.WSCreateDemoSession),
    WSR('/delete_sessions', cs.WSDeleteSessions),
    WSR('/wait_for_session_in_room', cs.WSRoomParticipant),
    WSR('/room_without_session/{room_name}', cs.WSRoomAdmin),
    WSR('/session_monitor/{code}', cs.WSSessionMonitor),
    WSR('/browser_bots_client/{session_code}', cs.WSBrowserBotsLauncher),
    WSR('/browser_bot_wait', cs.WSBrowserBot),
    WSR('/live', cs.LiveConsumer),
    WSR('/chat', cs.WSChat),
    WSR('/export', cs.WSExportData),
]
