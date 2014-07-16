# -*- coding: utf-8 -*-
"""Documentation at https://github.com/wickens/django-ptree-docs/wiki"""

from ptree.db import models
import ptree.models
from django.conf import settings
from django.utils.translation import ugettext_lazy as _

doc = """
Description of this app.
"""

class Subsession(ptree.models.BaseSubsession):

    name_in_url = '{{ app_name }}'


class Treatment(ptree.models.BaseTreatment):
    subsession = models.ForeignKey(Subsession)


class Match(ptree.models.BaseMatch):

    treatment = models.ForeignKey(Treatment)
    subsession = models.ForeignKey(Subsession)

    participants_per_match = 1


class Participant(ptree.models.BaseParticipant):

    match = models.ForeignKey(Match, null = True)
    treatment = models.ForeignKey(Treatment, null = True)
    subsession = models.ForeignKey(Subsession)

    # example field
    my_field = models.PositiveIntegerField(
        null=True,
        doc="""
        Description of this field, for documentation
        """
    )

    def set_payoff(self):
        self.payoff = 0 # change to whatever the payoff should be


def treatments():
    # add treatment parameters as arguments to create()
    # e.g. [Treatment.create(max_payoff=20), Treatment.create(max_payoff=20)]
    return [Treatment.create(label = '',)]