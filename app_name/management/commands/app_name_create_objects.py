from django.core.management.base import NoArgsCommand, make_option

from {{ app_name }}.models import Experiment, Treatment, Participant

def create_objects():

    # delete any existing objects from the DB since we are creating new ones
    Experiment.objects.all().delete()
    Treatment.objects.all().delete()
    Participant.objects.all().delete()

    # just an example. you can change this as you want.
    experiment = Experiment(randomization_mode = Experiment.SMOOTHING, 
                            description = 'Experiment with all treatments')
    experiment.save()

    number_of_treatments = 1 # change this number as you wish.

    for i in range(number_of_treatments):
        treatment = Treatment(experiment = experiment,
                        base_pay = 100,
                        # initialize other attributes here.
                        # The point of having multiple treatments is to make them distinct.
                        )
        treatment.save()

    number_of_participants = 20 # change this number as you wish

    for i in range(number_of_participants):
        participant = Participant(experiment = experiment)
        participant.save()

class Command(NoArgsCommand):

    help = "pTree ({{ app_name }}): Populate the database before launching, with Experiment, Treatments, and Participant objects."

    option_list = NoArgsCommand.option_list + (
        make_option('--verbose', action='store_true'),
    )

    def handle_noargs(self, **options):
        create_objects()

