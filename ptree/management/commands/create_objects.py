from django.core.management.base import BaseCommand, CommandError
from optparse import make_option
from django.utils.importlib import import_module
from django.conf import settings
import sys

class Command(BaseCommand):
    help = "pTree: Populate the database before launching, with Experiment, Treatments, and Participant objects."

    option_list = BaseCommand.option_list + (
        make_option('--app_name',
            type='str',
            dest='app_name',
            help='e.g. "dictator" or "ultimatum"'),

        make_option('--participants',
            type='int',
            dest='num_participants',
            help='Number of participants to pre-generate'),
    )

    def handle(self, *args, **options):
        app_name = options['app_name']
        if app_name not in settings.INSTALLED_PTREE_APPS:
            print 'Before running this command you need to add "{}" to INSTALLED_PTREE_APPS.'.format(app_name)
            sys.exit(0)
        admin_module = import_module('{}.models'.format(app_name))
        admin_module.create_objects(num_participants=options['num_participants'])
        print 'Created objects for {}'.format(app_name)