
import os
import channels.asgi
from . import configure_settings

configure_settings()
channel_layer = channels.asgi.get_channel_layer()

from otree.common_internal import (
    release_any_stale_locks, get_redis_conn  # noqa
)

# clear any tasks in Huey DB, so they don't pile up over time,
# especially if you run the server without the timeoutworker to consume the
# tasks.
# ideally we would only schedule a task in Huey if timeoutworker is running,
# so that we don't pile up messages that never get consumed, but I don't know
# how and when to check if Huey is running, in a performant way.
# this code is also in timeoutworker.
from huey.contrib.djhuey import HUEY  # noqa
HUEY.flush()

from otree.bots.browser import redis_flush_bots  # noqa
redis_flush_bots(get_redis_conn())

# needs to happen after Django setup
release_any_stale_locks()
