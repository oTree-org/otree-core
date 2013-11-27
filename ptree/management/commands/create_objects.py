from django.core.management.base import BaseCommand, CommandError
from optparse import make_option
from django.utils.importlib import import_module
from django.conf import settings
import sys

class Command(BaseCommand):
    help = "pTree: Populate the database before launching, with Experiment, Treatments, and Participant objects."
    args = '<app_name> <num_participants>'

    def handle(self, *args, **options):
        if len(args) != 2:
            raise CommandError("Wrong number of arguments (expecting 'mturk_pay app_label experiment_id'. Example: 'mturk_pay ultimatum 3')")
        else:
            app_name, num_participants = args
            if app_name not in settings.INSTALLED_PTREE_APPS:
                print 'Before running this command you need to add "{}" to INSTALLED_PTREE_APPS.'.format(app_name)
                return
            models_module = import_module('{}.models'.format(app_name))
            models_module.create_objects(num_participants=int(num_participants))
            print 'Created objects for {}'.format(app_name)