
#==============================================================================
# IMPORTS
#==============================================================================

import logging
import sys

from optparse import make_option

from django.core.management.base import BaseCommand

from otree.test import runner, client


#==============================================================================
# CONSTANTS
#==============================================================================

COVERAGE_CONSOLE = "console"
COVERAGE_HTML = "HTML"
COVERAGE_ALL = "all"


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
        make_option(
            '-c', '--coverage', action='store', dest='coverage',
            choices=(COVERAGE_ALL, COVERAGE_CONSOLE, COVERAGE_HTML),
            help='Execute code-coverage over the code of tested experiments'
        ),
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
        if options['verbosity'] < 2:
            logging.basicConfig(level=logging.WARNING)
            runner.logger.setLevel(logging.WARNING)
            client.logger.setLevel(logging.WARNING)

        coverage = options["coverage"]

        test_runner = runner.OTreeExperimentTestRunner(**options)

        if coverage:
            with runner.covering(test_labels) as coverage_report:
                failures = test_runner.run_tests(test_labels)
        else:
            failures = test_runner.run_tests(test_labels)

        if coverage:
            logger.info("Coverage Report")
            if coverage in [COVERAGE_CONSOLE, COVERAGE_ALL]:
                coverage_report.report()
            if coverage in [COVERAGE_HTML, COVERAGE_ALL]:
                html_coverage_results_dir = '_coverage_results'
                percent_coverage = coverage_report.html_report(
                    directory=html_coverage_results_dir
                )
                msg = ("See '{}/index.html' for detailed results.").format(
                    html_coverage_results_dir
                )
                logger.info(msg)

        if failures:
            sys.exit(bool(failures))
