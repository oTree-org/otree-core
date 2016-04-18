from channels.management.commands.runworker import Command as RunworkerCommand
import redis.exceptions
import sys

class Command(RunworkerCommand):

    def handle(self, *args, **options):
        try:
            super(Command, self).handle(*args, **options)
        except redis.exceptions.ConnectionError as e:
            if sys.version_info[0] == 2:
                raise
            else:
                # .with_traceback only works on Py3
                raise Exception('You need to install and run Redis.').with_traceback(e.__traceback__)


