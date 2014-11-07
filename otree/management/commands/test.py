import logging
import sys

from optparse import make_option

from django.conf import settings
from django.core.management.base import BaseCommand

from otree.test import core


class Command(BaseCommand):
    help = ('Discover and run experiment tests in the specified '
            'modules or the current directory.')
    args = '[experiment_name|experiment_name|experiment_name]...'

    requires_model_validation = False

    def execute(self, *args, **options):
        if int(options['verbosity']) > 0:
            logger = logging.getLogger('py.warnings')
            handler = logging.StreamHandler()
            logger.addHandler(handler)
        super(Command, self).execute(*args, **options)
        if int(options['verbosity']) > 0:
            logger.removeHandler(handler)

    def handle(self, *test_labels, **options):
        options['verbosity'] = int(options.get('verbosity'))
        test_runner = core.OTreeExperimentTestRunner(**options)
        failures = test_runner.run_tests(test_labels)

        if failures:
            sys.exit(bool(failures))
