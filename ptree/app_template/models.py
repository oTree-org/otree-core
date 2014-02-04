"""Documentation at http://django-ptree.readthedocs.org/en/latest/app.html"""

from ptree.db import models
import ptree.models
from django.conf import settings
from django.utils.translation import ugettext_lazy as _

class Experiment(ptree.models.BaseExperiment):

    name_in_url = '{{ app_name }}'

class Treatment(ptree.models.BaseTreatment):
    experiment = models.ForeignKey(Experiment)

    def sequence_of_views(self):
    
        import {{ app_name }}.views as views
        return [views.MyView]
                
class Match(ptree.models.BaseMatch):

    treatment = models.ForeignKey(Treatment)
    experiment = models.ForeignKey(Experiment)

    def is_ready_for_next_participant(self):
        return len(self.participants()) < self.treatment.participants_per_match

class Participant(ptree.models.BaseParticipant):

    match = models.ForeignKey(Match, null = True)
    treatment = models.ForeignKey(Treatment, null = True)
    experiment = models.ForeignKey(Experiment)


    my_field = models.BooleanField(
        default=False,
        doc='description of this field, for documentation'
    )

    def bonus(self):
        # make sure this doesn't trigger an exception if the match isn't finished.
        # return None if the bonus cannot be calculated yet.
        return None

def create_experiment_and_treatments():

    experiment = Experiment()
    experiment.save()

    # you can create more treatments. just make a loop.
    treatment = Treatment(experiment = experiment,
                          participants_per_match = 1,
                          label = '',
                          # other attributes here...
                          )
    treatment.save()

    return experiment