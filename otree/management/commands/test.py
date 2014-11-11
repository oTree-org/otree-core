
#==============================================================================
# IMPORTS
#==============================================================================

import logging
import sys

from optparse import make_option

from django.conf import settings
from django.core.management.base import BaseCommand

from otree.test import runner


#==============================================================================
# LOGGER
#==============================================================================

logger = logging.getLogger(__name__)


#==============================================================================
# COMMAND
#==============================================================================

class Command(BaseCommand):
    help = ('Discover and run experiment tests in the specified '
            'modules or the current directory.')
    option_list = BaseCommand.option_list + (
        make_option('-c', '--coverare', action='store_true', dest='coverage',
        help='Execute code-coverage over the code of tested experiments'),
    )
    args = '[experiment_name|experiment_name|experiment_name]...'

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
        coverage = options["coverage"]

        test_runner = runner.OTreeExperimentTestRunner(**options)

        if coverage:
            with runner.covering(test_labels) as coverage:
                failures = test_runner.run_tests(test_labels)
        else:
            failures = test_runner.run_tests(test_labels)

        if coverage:
            logger.info("Coverage Report")
            coverage.report()
            html_coverage_results_dir = '_coverage_results'
            percent_coverage = coverage.html_report(
                directory=html_coverage_results_dir
            )
            msg = ("See '{}/index.html' for detailed results.").format(
                html_coverage_results_dir
            )
            logger.info(msg)

        if failures:
            sys.exit(bool(failures))
