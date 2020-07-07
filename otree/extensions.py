from importlib import import_module
from django.conf import settings
import importlib.util
import sys


"""
(THIS IS CURRENTLY PRIVATE API, MAY CHANGE WITHOUT NOTICE)

To create an oTree extension, add a package called ``otree_extensions``
to your app, and add the app name in settings.py to EXTENSION_APPS. 
It can contain any of the following submodules:

urls.py
-------

should contain a variable ``urlpatterns``, which will be appended to
oTree's built-in URL patterns.

routing.py
----------

Should contain a variable ``websocket_routes``,
with a list of channel routes, as described in the Django channels documentation.

admin.py
--------

This module allows you to define custom data exports that will be included
in oTree's data export page. Define a variable ``data_export_views``,
which is a list of Django class-based views (see Django docs).

Each view should define a ``get()`` method with the following signature::

    def get(self, request, *args, **kwargs):

This method should return an HTTP response with
the exported data (e.g. CSV, XLSX, JSON, etc), using the appropriate MIME type
on the HTTP response.

Each view must also have the following attributes:

-   ``url_pattern``: the URL pattern string, e.g. '^mychat_export/$'
-   ``url_name``: see Django docs on reverse resolution of URLs, e.g. 'mychat_export'
-   ``display_name``: The text of the download hyperlink on the data export page
    (e.g. "Chat Data Export")

You don't need to worry about login_required and AUTH_LEVEL;
oTree will handle this automatically.
"""

from logging import getLogger

logger = getLogger(__name__)


def get_extensions_modules(submodule_name):
    modules = []
    find_spec = importlib.util.find_spec
    for app_name in getattr(settings, 'EXTENSION_APPS', []):
        package_dotted = f'{app_name}.otree_extensions'
        submodule_dotted = f'{package_dotted}.{submodule_name}'
        # need to check if base package exists; otherwise we get ImportError
        if find_spec(package_dotted) and find_spec(submodule_dotted):
            modules.append(import_module(submodule_dotted))
    return modules


def get_extensions_data_export_views():
    view_classes = []
    for module in get_extensions_modules('admin'):
        view_classes += getattr(module, 'data_export_views', [])
    return view_classes
