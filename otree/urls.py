import inspect
from importlib import import_module
from pathlib import Path

from starlette.endpoints import HTTPEndpoint
from starlette.responses import RedirectResponse
from starlette.routing import Route, Mount

from otree import common, settings
from otree.channels.routing import websocket_routes
from otree.common2 import static_files_app

ALWAYS_UNRESTRICTED = {
    # REST views don't need to be here because they don't use the
    # _login_required flag to begin with. they are automatically open.
    'AssignVisitorToRoom',
    'InitializeParticipant',
    'Login',
    'MTurkLandingPage',
    'MTurkStart',
    'JoinSessionAnonymously',
    'OutOfRangeNotification',
    'BrowserBotStartLink',
    'SaveDB',
    'WSSubsessionWaitPage',
    'WSGroupWaitPage',
    'LiveConsumer',
    'WSGroupByArrivalTime',
    'DetectAutoAdvance',
    'WSRoomParticipant',
    'WSBrowserBotsLauncher',
    'WSBrowserBot',
    'WSChat',
}


UNRESTRICTED_IN_DEMO_MODE = ALWAYS_UNRESTRICTED.union(
    {
        'AdminReport',
        'AdvanceSession',
        'CreateDemoSession',
        'DemoIndex',
        'SessionSplitScreen',
        'SessionDescription',
        'SessionMonitor',
        'SessionPayments',
        'SessionData',
        'SessionDataAjax',
        'SessionStartLinks',
        'WSCreateDemoSession',
        'WSSessionMonitor',
    }
)


def view_classes_from_module(module_name):
    views_module = import_module(module_name)

    return [
        ViewCls
        for _, ViewCls in inspect.getmembers(views_module)
        if hasattr(ViewCls, 'url_pattern')
        and inspect.getmodule(ViewCls) == views_module
    ]


def url_patterns_from_app_pages(app_name, name_in_url):
    pages_module = common.get_pages_module(app_name)
    is_noself = common.is_noself(app_name)

    page_urls = []
    for ViewCls in pages_module.page_sequence:
        ViewCls.is_noself = is_noself
        # don't set it back because this just happens on startup

        url_pattern = ViewCls.url_pattern(name_in_url)
        url_name = ViewCls.url_name()
        page_urls.append(Route(url_pattern, ViewCls, name=url_name))

    return page_urls


def url_patterns_from_builtin_module(module_name: str):

    all_views = view_classes_from_module(module_name)

    view_urls = []
    for ViewCls in all_views:
        # automatically assign URL name for reverse(), it defaults to the
        # class's name
        url_name = getattr(ViewCls, 'url_name', ViewCls.__name__)

        ViewCls._requires_login = {
            'STUDY': url_name not in ALWAYS_UNRESTRICTED,
            'DEMO': url_name not in UNRESTRICTED_IN_DEMO_MODE,
            '': False,
            None: False,
        }[settings.AUTH_LEVEL]

        url_pattern = ViewCls.url_pattern
        if callable(url_pattern):
            url_pattern = url_pattern()

        view_urls.append(Route(url_pattern, ViewCls, name=url_name))

    return view_urls


def get_urlpatterns():

    routes = []

    used_names_in_url = set()
    for app_name in settings.OTREE_APPS:
        Constants = common.get_constants(app_name)
        name_in_url = Constants.get_normalized('name_in_url')
        if name_in_url in used_names_in_url:
            msg = (
                "App {} has name_in_url='{}', " "which is already used by another app"
            ).format(app_name, name_in_url)
            raise ValueError(msg)

        used_names_in_url.add(name_in_url)

        routes += url_patterns_from_app_pages(app_name, name_in_url)

    routes += url_patterns_from_builtin_module('otree.views.participant')
    routes += url_patterns_from_builtin_module('otree.views.demo')
    routes += url_patterns_from_builtin_module('otree.views.admin')
    routes += url_patterns_from_builtin_module('otree.views.room')
    routes += url_patterns_from_builtin_module('otree.views.mturk')
    routes += url_patterns_from_builtin_module('otree.views.export')
    routes += url_patterns_from_builtin_module('otree.views.rest')
    routes += websocket_routes
    routes += [
        Mount('/static', app=static_files_app, name="static",),
        Route("/favicon.ico", endpoint=Favicon),
        Route('/', endpoint=HomeRedirect),
    ]

    return routes


class Favicon(HTTPEndpoint):
    async def get(self, request):
        return RedirectResponse('/static/favicon.ico')


class HomeRedirect(HTTPEndpoint):
    async def get(self, request):
        return RedirectResponse('/demo')


routes = get_urlpatterns()
