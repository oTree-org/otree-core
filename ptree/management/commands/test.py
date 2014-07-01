from django.utils.importlib import import_module
from django.core.management.base import BaseCommand, CommandError
from django.conf import settings
from ptree.session import create_session, session_types_as_dict
import os.path
import ptree.test.run
import coverage

modules_to_include_in_coverage = ['models', 'tests', 'views', 'forms']

class Command(BaseCommand):
    help = "pTree: Run the test bots for a session."
    args = '[session_type]'

    def handle(self, *args, **options):

        print 'Creating session...'
        if len(args) > 1:
            raise CommandError("Wrong number of arguments (expecting '{}')".format(self.args))

        if len(args) == 1:
            name = args[0]
        else:
            name = None

        app_labels = session_types_as_dict()[name].subsession_apps
        package_names = []
        cov = coverage.coverage(source=package_names)
        cov.start()

        session = create_session(name)
        session.label = '{} [test]'.format(session.label)
        session.save()

        ptree.test.run.run(session)

        cov.stop()
        print cov.html_report(directory='covhtml')





