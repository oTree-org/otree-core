from otree.test.run import run_all_sessions_without_coverage
from django.core.management.base import BaseCommand, CommandError


class Command(BaseCommand):
    help = "oTree: Run the test bots for all sessions."

    def handle(self, *args, **options):

        if len(args) > 0:
            raise CommandError("This command does not accept arguments ({})".format(args))
        run_all_sessions_without_coverage()



