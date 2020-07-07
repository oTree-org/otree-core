import os
import django
from channels.routing import get_default_application
from . import configure_settings
from django.conf import settings

# needed if uvicorn is launched multi-process
if not settings.configured:
    configure_settings()
    django.setup()

application = get_default_application()

# clear any tasks in Huey DB, so they don't pile up over time,
# especially if you run the server without the timeoutworker to consume the
# tasks.
# ideally we would only schedule a task in Huey if timeoutworker is running,
# so that we don't pile up messages that never get consumed, but I don't know
# how and when to check if Huey is running, in a performant way.
# this code is also in timeoutworker.
from huey.contrib.djhuey import HUEY  # noqa
import redis.exceptions
try:
    HUEY.flush()
except redis.exceptions.ConnectionError:
    # maybe Redis is not running
    pass
