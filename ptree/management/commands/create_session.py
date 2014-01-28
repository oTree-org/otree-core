from django.utils.importlib import import_module
from django.core.management.base import BaseCommand, CommandError
from django.conf import settings
import os.path

def directory_name(path):
    return os.path.basename(os.path.normpath(path))

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


        session_module = import_module('{}.{}'.format(directory_name(settings.BASE_DIR), 'session'))
        session_module.create_session(name)


