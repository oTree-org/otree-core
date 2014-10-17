import sys
from otree.test.run import run_session_with_coverage
from django.core.management.base import BaseCommand, CommandError

class Command(BaseCommand):
    help = "oTree: Run the test bots for a session."
    args = '[session_type]'

    def handle(self, *args, **options):

        if len(args) > 1:
            raise CommandError("Wrong number of arguments (expecting '{}')".format(self.args))

        if len(args) == 1:
            session_type_name = args[0]
        else:
            session_type_name = None

        success = run_session_with_coverage(session_type_name)
        if not success:
            sys.exit(1)
        else:
            sys.exit(0)
