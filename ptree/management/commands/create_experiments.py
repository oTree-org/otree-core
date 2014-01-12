from django.utils.importlib import import_module
from django.core.management.base import BaseCommand, CommandError
from django.conf import settings

class Command(BaseCommand):
    help = "pTree: Create a sequence of experiments."
    args = '[name]'

    def handle(self, *args, **options):
        print 'Creating sequence of experiments...'
        if len(args) >= 1:
            raise CommandError("Wrong number of arguments (expecting '{}')".format(self.args))

        if len(args) == 1:
            name = args[0]
        else:
            name = None

        sequence_module = import_module('{}.{}'.format(settings.PROJECT_DIRECTORY, 'sequence_of_experiments'))
        sequence_module.create_sequence_of_experiments(name)


