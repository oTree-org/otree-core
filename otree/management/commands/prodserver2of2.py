# run the worker to enforce page timeouts
# even if the user closes their browser
from huey.contrib.djhuey.management.commands.run_huey import Command as HueyCommand
import redis.exceptions
import os
import sys


class Command(HueyCommand):
    def handle(self, *args, **options):
        # clear any tasks in Huey DB, so they don't pile up over time,
        # especially if you run the server without the timeoutworker to consume
        # the tasks.
        # this code is also in asgi.py. it should be in both places,
        # to ensure the database is flushed in all circumstances.
        from huey.contrib.djhuey import HUEY

        if not os.environ.get('REDIS_URL'):
            sys.exit('REDIS_URL env var must be defined')

        try:
            HUEY.flush()
        except redis.exceptions.ConnectionError as exc:
            sys.exit(f'Could not connect to Redis: {exc}')

        super().handle(*args, **options)
