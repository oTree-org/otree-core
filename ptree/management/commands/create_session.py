from django.core.management.base import BaseCommand, CommandError
from ptree.session import create_session

class Command(BaseCommand):
    help = "pTree: Create a session."
    args = '[name]'

    def handle(self, *args, **options):
        print 'Creating session...'
        if len(args) > 1:
            raise CommandError("Wrong number of arguments (expecting '{}')".format(self.args))

        if len(args) == 1:
            name = args[0]
        else:
            name = None

        create_session(name)