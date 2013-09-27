from django.db import models
import ptree.models.common
from django.template import defaultfilters

import abc

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
    
    INDEPENDENT, SMOOTHING, = range(2)

    RANDOMIZATION_MODE_CHOICES = (

        # random.choice
        (INDEPENDENT, 'Independent'),

        # assign to the treatment that has the fewest data points
        (SMOOTHING, 'Smoothing'),
    )

    randomization_mode = models.SmallIntegerField(choices = RANDOMIZATION_MODE_CHOICES)

    def __unicode__(self):
        
        if self.description:
            s = '{}, '.format(self.description)
        else:
            s = ''

        MAX_NUMBER_OF_TREATMENT_CHARS = 100
        treatment_listing = ', '.join([t.__unicode__() for t in self.treatment_set.all()])

        s += 'code: {}, mode: {}, treatments: {} [{}]'.format(self.code, 
                                                              self.RANDOMIZATION_MODE_CHOICES[self.randomization_mode][1], 
                                                              len(self.treatment_set.all()), 
                                                              treatment_listing)

        s = defaultfilters.truncatechars(s, 150)

        return s


    class Meta:
        abstract = True

    

