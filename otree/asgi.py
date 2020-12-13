from starlette.applications import Starlette
from . import settings
from .urls import routes
from .middleware import middlewares
from starlette.routing import NoMatchFound

app = Starlette(debug=settings.DEBUG, routes=routes, middleware=middlewares)

# alias like django reverse()
def reverse(name, **path_params):
    try:
        return app.url_path_for(name, **path_params)
    except NoMatchFound as exc:
        raise NoMatchFound(f'{name}, {path_params}') from None
