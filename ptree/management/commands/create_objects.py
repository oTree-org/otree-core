from django.core.management.base import BaseCommand, CommandError
from optparse import make_option
from django.utils.importlib import import_module

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
        admin_module = import_module('{}.models'.format(options['app_name']))
        admin_module.create_objects(num_participants=options['num_participants'])
        print 'Created objects for {}'.format(options['app_name'])