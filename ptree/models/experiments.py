from django.db import models
import ptree.models.common
from django.template import defaultfilters
import random

class BaseExperiment(models.Model):
    """Base class for all Experiments.
    An Experiment is a randomization between Treatments.

    Example:

    You could have 2 Treatments:
    - Prisoner's Dilemma with high payoff (users play for max reward of $5)
    - Prisoner's Dilemma with low payoff (users play for max reward of $1)

    You're interested in seeing how the payoff affects users' behavior.

    So, you define those 2 Treatments,
    and then create an Experiment that randomly assigns users to one or the other.
    """

    description = models.TextField(max_length = 1000, null = True, blank = True)
    code = ptree.models.common.RandomCharField(length=8) 

    # code to pass in URL to enable demo mode, which skips randomization
    # and instead assigns you to a pre-determined treatment.
    demo_code = ptree.models.common.RandomCharField(length=8)

    def weighted_randomization_choice(self, choices):
       total = sum(w for c, w in choices)
       r = random.uniform(0, total)
       upto = 0
       for c, w in choices:
          if upto + w > r:
             return c
          upto += w

    def pick_treatment_for_incoming_participant(self):
        """pick a treatment according to randomization algorithm."""
        choices = [(treatment, treatment.randomization_weight) for treatment in self.treatment_set.all()]
        treatment = self.weighted_randomization_choice(choices)
        return treatment

    def treatments(self):
        return self.treatment_set.all()

    def __unicode__(self):
        
        if self.description:
            s = '{}, '.format(self.description)
        else:
            s = ''

        MAX_NUMBER_OF_TREATMENT_CHARS = 100
        treatment_listing = ', '.join([t.__unicode__() for t in self.treatment_set.all()])

        s += 'code: {}, treatments: {} [{}]'.format(self.code,
                                                  len(self.treatments()),
                                                  treatment_listing)

        s = defaultfilters.truncatechars(s, 150)

        return s


    class Meta:
        abstract = True

    

