import ptree.common
from django.utils.importlib import import_module
from django.core.management.base import BaseCommand, CommandError
from django.conf import settings
import ptree.sequence_of_experiments.models
from optparse import make_option
import ptree.views.abstract
import random

class Command(BaseCommand):
    help = "pTree: Create a sequence of experiments."
    args = 'name'

    def handle(self, *args, **options):
        print 'Creating sequence of experiments...'
        if len(args) != 1:
            raise CommandError("Wrong number of arguments (expecting '{}')".format(self.args))

        sequence_module = import_module('{}.{}'.format(settings.PROJECT_DIRECTORY), 'sequence_of_experiments')


