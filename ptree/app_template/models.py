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
    # <built-in>
    subsession = models.ForeignKey(Subsession)
    # </built-in>


class Match(ptree.models.BaseMatch):
    # <built-in>
    treatment = models.ForeignKey(Treatment)
    subsession = models.ForeignKey(Subsession)
    # </built-in>

    participants_per_match = 1


class Participant(ptree.models.BaseParticipant):
    # <built-in>
    match = models.ForeignKey(Match, null = True)
    treatment = models.ForeignKey(Treatment, null = True)
    subsession = models.ForeignKey(Subsession)
    # </built-in>

    def other_participant(self):
        """Returns other participant in match. Only valid for 2-player matches."""
        return self.other_participants_in_match()[0]

    # example field
    my_field = models.MoneyField(
        default=None,
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
    return [Treatment.create()]