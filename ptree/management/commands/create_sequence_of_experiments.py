import ptree.common
from django.utils.importlib import import_module
from django.core.management.base import BaseCommand, CommandError

class Command(BaseCommand):
    help = "pTree: Create a sequence of experiments."
    args = 'num_participants app_name [app_name] ...'

    def handle(self, *args, **options):
        if len(args) < 2:
            raise CommandError("Wrong number of arguments (expecting '{}')".format(self.args))

        num_participants = int(args[0])
        app_names = args[1:]
        experiments = []
        for app_name in app_names:
            models_module = import_module('{}.models').format(app_name)
            # fixme: this function does not return experiment.
            experiment = models_module.create_objects(num_participants=num_participants)
            experiments.append(experiment)

        ptree.common.create_sequence_of_experiments(experiments)