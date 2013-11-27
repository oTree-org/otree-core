import ptree.common
from django.utils.importlib import import_module
from django.core.management.base import BaseCommand, CommandError
import ptree.stuff.models

class Command(BaseCommand):
    help = "pTree: Create a sequence of experiments, from experiments that have already been created."
    args = 'app_name experiment_id [app_name experiment_id] ...'

    def handle(self, *args, **options):
        experiments = []
        for i in range(0, len(args), 2):
            app_name = args[i]
            experiment_id = int(args[i + 1])
            models_module = import_module('{}.models'.format(app_name))
            experiment = models_module.Experiment.objects.get(pk = experiment_id)
            experiments.append(experiment)
        seq = ptree.stuff.models.SequenceOfExperiments()
        seq.add_experiments(experiments)
