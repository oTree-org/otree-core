import inspect
from importlib import import_module
from otree.channels.routing import websocket_routes

from otree import common, settings
from starlette.routing import Route, Mount
from starlette.staticfiles import StaticFiles
from starlette.endpoints import HTTPEndpoint
from starlette.responses import RedirectResponse

ALWAYS_UNRESTRICTED = {
    'AssignVisitorToRoom',
    'InitializeParticipant',
    'Login',
    'MTurkLandingPage',
    'MTurkStart',
    'JoinSessionAnonymously',
    'OutOfRangeNotification',
    'RESTCreateSession',
    'RESTSessionVars',
    'PostParticipantVarsThroughREST',
    'CreateBrowserBotsSession',
    'CloseBrowserBotsSession',
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


import importlib.util, os


class OTreeStaticFiles(StaticFiles):
    # copied from starlette, just to change 'statics' to 'static',
    # and to fail silently if the dir does not exist.
    def get_directories(self, directory, packages):
        directories = []
        if directory is not None:
            directories.append(directory)

        for package in packages or []:
            spec = importlib.util.find_spec(package)
            assert (
                spec is not None and spec.origin is not None
            ), f"Package {package!r} could not be found, or maybe __init__.py is missing"
            package_directory = os.path.normpath(
                os.path.join(spec.origin, "..", "static")
            )
            if os.path.isdir(package_directory):
                directories.append(package_directory)

        return directories


def url_patterns_from_app_pages(module_name, name_in_url):
    views_module = import_module(module_name)

    view_urls = []
    for ViewCls in views_module.page_sequence:

        url_pattern = ViewCls.url_pattern(name_in_url)
        url_name = ViewCls.url_name()
        view_urls.append(Route(url_pattern, ViewCls, name=url_name))

    return view_urls


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
        models_module = common.get_models_module(app_name)
        name_in_url = models_module.Constants.name_in_url
        if name_in_url in used_names_in_url:
            msg = (
                "App {} has Constants.name_in_url='{}', "
                "which is already used by another app"
            ).format(app_name, name_in_url)
            raise ValueError(msg)

        used_names_in_url.add(name_in_url)

        views_module = common.get_pages_module(app_name)
        routes += url_patterns_from_app_pages(views_module.__name__, name_in_url)

    routes += url_patterns_from_builtin_module('otree.views.participant')
    routes += url_patterns_from_builtin_module('otree.views.demo')
    routes += url_patterns_from_builtin_module('otree.views.admin')
    routes += url_patterns_from_builtin_module('otree.views.room')
    routes += url_patterns_from_builtin_module('otree.views.mturk')
    routes += url_patterns_from_builtin_module('otree.views.export')
    routes += url_patterns_from_builtin_module('otree.views.rest')
    routes += websocket_routes
    routes += [
        Mount(
            '/static',
            app=OTreeStaticFiles(
                directory='_static', packages=['otree'] + settings.OTREE_APPS
            ),
            name="static",
        ),
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
