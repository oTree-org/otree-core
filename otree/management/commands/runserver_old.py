from channels.management.commands.runserver import Command as RunserverCommand
import redis.exceptions
import sys

class Command(RunserverCommand):

    def handle(self, *args, **options):
        try:
            super(Command, self).handle(*args, **options)
        except redis.exceptions.ConnectionError as e:
            if sys.version_info[0] == 2:
                raise
            else:
                # .with_traceback only works on Py3
                raise Exception(
                    'This version of oTree requires Redis to be installed '
                    'and running on port 6379 by default.'
                ).with_traceback(e.__traceback__)
