"""public api"""

import otree.sessionlib.models

from otree.views.abstract import (
    InitializePlayer,
    InitializeExperimenter,
)

from importlib import import_module
abstract = import_module('otree.views.abstract')

class WaitPage(abstract.WaitPage):

    def body_text(self):
        return super(WaitPage, self).body_text()

    def title_text(self):
        return super(WaitPage, self).title_text()

    scope = None

    def after_all_players_arrive(self):
        return super(WaitPage, self).after_all_players_arrive()

class Page(abstract.PlayerUpdateView):

    def variables_for_template(self):
        return super(Page, self).variables_for_template()

    def after_valid_form_submission(self):
        return super(Page, self).after_valid_form_submission()

    def get_form_class(self):
        return super(Page, self).get_form_class()

    def participate_condition(self):
        return super(Page, self).participate_condition()

    template_name = None

    # prefix with "form_" so that it's clear these refer to the form
    # otherwise someone might confuse 'fields' with variables_for_template
    form_model = abstract.PlayerUpdateView.model
    form_fields = abstract.PlayerUpdateView.fields

    time_limit_auto_advance = True

    def time_limit_in_seconds(self):
        return super(Page, self).time_limit_in_seconds()

class ExperimenterPage(abstract.ExperimenterUpdateView):

    def variables_for_template(self):
        return super(ExperimenterPage, self).variables_for_template()

    def after_valid_form_submission(self):
        return super(ExperimenterPage, self).after_valid_form_submission()

    def get_form_class(self):
        return super(ExperimenterPage, self).get_form_class()

    def participate_condition(self):
        return super(ExperimenterPage, self).participate_condition()

    template_name = None
