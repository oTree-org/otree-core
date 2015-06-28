from __future__ import absolute_import

import importlib


def setup_celery_app():
    from celery import Celery
    from django.conf import settings

    app = Celery('otree')

    # Using a string here means the worker will not have to
    # pickle the object when using Windows.
    app.config_from_object('django.conf:settings')
    app.autodiscover_tasks(lambda: settings.INSTALLED_APPS)

    return app


def load_celery_app():
    """
    This either loads the app configured in ``settings.CELERY_APP``.

    The ``CELERY_APP`` settings needs to be the same format as the ``--app``
    commandline option for celery, e.g. ``my.module:app_variable_name``.
    """

    from django.conf import settings
    import_path = settings.CELERY_APP

    if ':' in import_path:
        path, variable = import_path.split(':')
    else:
        path = import_path
        variable = 'app'
    app_module = importlib.import_module(path)
    app_variable = getattr(app_module, variable)
    return app_variable
