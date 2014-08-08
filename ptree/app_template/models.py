# -*- coding: utf-8 -*-
"""Documentation at https://github.com/wickens/django-ptree-docs/wiki"""

from ptree.db import models
import ptree.models
from ptree.common import Money, money_range

author = 'Your name here'

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

    def other_participant(self):
        """Returns other participant in match. Only valid for 2-player matches."""
        return self.other_participants_in_match()[0]

    # example field
    my_field = models.MoneyField(
        null=True,
        doc="""
        Description of this field, for documentation
        """
    )

    def set_payoff(self):
        self.payoff = 0 # change to whatever the payoff should be

    def role(self):
        # you can make this depend of self.index_among_participants_in_match
        return ''

def treatments():
    # add treatment parameters as arguments to create()
    # e.g. [Treatment.create(max_payoff=20), Treatment.create(max_payoff=20)]
    return [Treatment.create(label = '',)]