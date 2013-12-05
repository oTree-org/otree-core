import ptree.common
from django.utils.importlib import import_module
from django.core.management.base import BaseCommand, CommandError
from django.conf import settings
from ptree.sequence_of_experiments.models import SequenceOfExperiments
from optparse import make_option
import ptree.views.abstract
import random

class Command(BaseCommand):
    help = "pTree: Create a sequence of experiments."
    args = 'num_participants app_name [app_name] ...'

    option_list = BaseCommand.option_list + (
        make_option('--is-for-mturk',
            action='store_true',
            dest='is_for_mturk',
            default=False,
            help='Whether the experiment will be run on Amazon Mechanical Turk'),
        make_option('--pregenerate-matches',
            action='store_true',
            dest='pregenerate_matches',
            default=False,
            help='Whether to pre-generate Matches and assign Participants to them on creation'),
        make_option('--name',
            action='store',
            dest='name',
            default=None,
            help='The name of the sequence of experiments'),
    )

    def handle(self, *args, **options):
        print 'Creating sequence of experiments...'
        if len(args) < 2:
            raise CommandError("Wrong number of arguments (expecting '{}')".format(self.args))

        seq = SequenceOfExperiments(is_for_mturk = options['is_for_mturk'],
                                    pregenerate_matches = options['pregenerate_matches'],
                                    name = options['name'])
        seq.save()


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


            if seq.pregenerate_matches:
                participants = list(experiment.participants())
                random.shuffle(participants)
                for participant in participants:
                    participant.treatment = experiment.pick_treatment_for_incoming_participant()
                    ptree.views.abstract.configure_match(models_module.Match, participant)
                    participant.save()

            print 'Created objects for {}'.format(app_name)
            experiments.append(experiment)


        seq.add_experiments(experiments)