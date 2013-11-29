import ptree.common
from django.utils.importlib import import_module
from django.core.management.base import BaseCommand, CommandError
from django.conf import settings
from ptree.sequence_of_experiments.models import SequenceOfExperiments

class Command(BaseCommand):
    help = "pTree: Create a sequence of experiments."
    args = 'num_participants app_name [app_name] ...'

    def handle(self, *args, **options):
        print 'Creating sequence of experiments...'
        if len(args) < 2:
            raise CommandError("Wrong number of arguments (expecting '{}')".format(self.args))

        num_participants = int(args[0])
        app_names = args[1:]
        experiments = []
        for app_name in app_names:
            if app_name not in settings.INSTALLED_PTREE_APPS:

                print 'Before running this command you need to add "{}" to INSTALLED_PTREE_APPS.'.format(app_name)
                return

            models_module = import_module('{}.models'.format(app_name))
            experiment = models_module.create_experiment_and_treatments()
            for i in range(num_participants):
                participant = models_module.Participant(experiment = experiment)
                participant.save()

            print 'Created objects for {}'.format(app_name)
            experiments.append(experiment)

        #TODO: allow passing in a --name parameter
        seq = ptree.sequence_of_experiments.models.SequenceOfExperiments()
        seq.add_experiments(experiments)