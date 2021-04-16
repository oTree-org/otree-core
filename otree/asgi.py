from starlette.applications import Starlette
from starlette.middleware import Middleware
from starlette.responses import HTMLResponse
from starlette.routing import NoMatchFound

from otree import errorpage
from otree.database import save_sqlite_db
from . import middleware
from . import settings
from .errorpage import OTreeServerErrorMiddleware
from .patch import ExceptionMiddleware
from .urls import routes


class OTreeStarlette(Starlette):
    def build_middleware_stack(self):

        debug = self.debug
        error_handler = None
        exception_handlers = {}

        for key, value in self.exception_handlers.items():
            if key in (500, Exception):
                error_handler = value
            else:
                exception_handlers[key] = value

        # By default Starlette puts ServerErrorMiddleware outside of all user middleware,
        # but I need to reverse that, because if we roll back the transaction before the error page
        # is displayed, it will show incorrect field values for a model instance's __repr__.
        middlewares = [
            Middleware(middleware.CommitTransactionMiddleware),
            Middleware(OTreeServerErrorMiddleware, handler=error_handler, debug=debug),
            Middleware(middleware.PerfMiddleware),
            Middleware(middleware.SessionMiddleware, secret_key=middleware._SECRET),
            Middleware(ExceptionMiddleware, handlers=exception_handlers, debug=debug),
        ]

        app = self.router
        for cls, options in reversed(middlewares):
            app = cls(app=app, **options)
        return app


ERR_500 = 500


async def server_error(request, exc):
    return HTMLResponse(content=HTML_500_PAGE, status_code=ERR_500)


app = OTreeStarlette(
    debug=settings.DEBUG,
    routes=routes,
    exception_handlers={ERR_500: server_error},
    on_shutdown=[save_sqlite_db],
)

# alias like django reverse()
def reverse(name, **path_params):
    try:
        return app.url_path_for(name, **path_params)
    except NoMatchFound as exc:
        raise NoMatchFound(f'{name}, {path_params}') from None


ERR_500_EXPLANATION = """
<p>
  For security reasons, the error is not displayed here.
  You can view it with one of the below techniques:
</p>

<ul>
    <li>Delete the <code>OTREE_PRODUCTION</code> environment variable and reload this page</li>
    <li>Look at your Sentry messages (see the docs on how to enable Sentry)</li>
    <li>Look at the server logs</li>
</ul>
"""

# 500 page should look like the debug 500 page so that people make the connection
HTML_500_PAGE = errorpage.TEMPLATE.format(
    styles=errorpage.STYLES,
    otree_styles=errorpage.OTREE_STYLES,
    tab_title="Application error (500)",
    error="",
    ibis_html='',
    exc_html=ERR_500_EXPLANATION,
    js='',
)
