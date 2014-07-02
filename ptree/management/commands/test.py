from django.utils.importlib import import_module
import sys
from django.core.management.base import BaseCommand, CommandError
from django.conf import settings
from ptree.session import create_session, session_types_as_dict
import os.path
import ptree.test.run
import coverage
import itertools
from django.core.management import call_command
from ptree.constants import special_category_bots

modules_to_include_in_coverage = ['models', 'tests', 'views', 'forms']

class Command(BaseCommand):
    help = "pTree: Run the test bots for a session."
    args = '[session_type]'

    def handle(self, *args, **options):

        print 'Creating session...'
        if len(args) > 1:
            raise CommandError("Wrong number of arguments (expecting '{}')".format(self.args))

        if len(args) == 1:
            type = args[0]
        else:
            type = None

        app_labels = session_types_as_dict()[type].subsession_apps

        package_names = []
        for app_label in app_labels:
            for module_name in modules_to_include_in_coverage:
                package_names.append('{}.{}'.format(app_label, module_name))
        package_names = itertools.chain(package_names)

        cov = coverage.coverage(source=package_names)
        cov.start()

        # force models.py to get loaded for coverage
        for app_label in app_labels:
            reload(sys.modules['{}.models'.format(app_label)])


        session = create_session(type=type, special_category=special_category_bots)
        session.label = '{} [test]'.format(session.label)
        session.save()

        ptree.test.run.run(session)

        cov.stop()
        html_coverage_results_dir = '_coverage_results'
        percent_coverage = cov.html_report(directory=html_coverage_results_dir)
        print 'Tests ran with {}% coverage. See "{}/index.html" for detailed results.'.format(
            int(percent_coverage),
            html_coverage_results_dir
        )





