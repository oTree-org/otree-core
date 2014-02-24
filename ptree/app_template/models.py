# -*- coding: utf-8 -*-
"""Documentation at http://django-ptree.readthedocs.org/en/latest/app.html"""

from ptree.db import models
import ptree.models
from django.conf import settings
from django.utils.translation import ugettext_lazy as _

class Subsession(ptree.models.BaseSubsession):

    name_in_url = '{{ app_name }}'

class Treatment(ptree.models.BaseTreatment):
    subsession = models.ForeignKey(Subsession)

    def pages(self):
    
        import {{ app_name }}.views as views
        return [views.MyView]

class Match(ptree.models.BaseMatch):

    treatment = models.ForeignKey(Treatment)
    subsession = models.ForeignKey(Subsession)

class Participant(ptree.models.BaseParticipant):

    match = models.ForeignKey(Match, null = True)
    treatment = models.ForeignKey(Treatment, null = True)
    subsession = models.ForeignKey(Subsession)

    # example field
    my_field = models.PositiveIntegerField(
        null=True,
        verbose_name="What is your age?",
        doc="""
        Description of this field, for documentation
        """
    )

def create_subsession_and_treatments():

    subsession = Subsession()
    subsession.save()

    # you can create more treatments. just make a loop.
    treatment = Treatment(
        subsession = subsession,
        participants_per_match = 1,
        label = '',
        # other attributes here...
    )
    treatment.save()

    return subsession