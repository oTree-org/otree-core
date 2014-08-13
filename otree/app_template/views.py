# -*- coding: utf-8 -*-
import otree.views
import otree.views.concrete
import {{ app_name }}.forms as forms
from {{ app_name }}.utilities import Page, MatchWaitPage, SubsessionWaitPage
from otree.common import Money, money_range

def variables_for_all_templates(self):
    return {
        # example:
        #'my_field': self.player.my_field,
    }

class Introduction(Page):

    def participate_condition(self):
        return True

    template_name = '{{ app_name }}/MyPage.html'

    def get_form_class(self):
        return forms.MyForm

    def variables_for_template(self):
        return {
            'my_variable_here': 1,
        }

    def after_valid_form_submission(self):
        """If all you need to do is save the form to the database,
        this can be left blank or omitted."""

class ResultsWaitPage(MatchWaitPage):

    def action(self):
        self.match.set_payoffs()

class Results(Page):

    template_name = '{{ app_name }}/Results.html'

def pages():
    return [
        Introduction,
        ResultsWaitPage,
        Results
    ]