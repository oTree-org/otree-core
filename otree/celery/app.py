"""
This file defines the app that should be used by celery in order to boot the
celery task queue.

If you want to use your own celery app with custom configuration, then override
the ``CELERY_APP`` setting.

To run celery, execute::

    python manage.py celery worker --app=otree.celery.app --loglevel=INFO

See http://www.celeryproject.org/ for more information.
"""
import os
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'settings')

from otree.celery.setup import setup_celery_app

# using huey instead
#app = setup_celery_app()
