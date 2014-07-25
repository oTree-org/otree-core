"""public api"""

from ptree.views.abstract import (
    InitializeParticipant,
    InitializeExperimenter,
)

from importlib import import_module
abstract = import_module('ptree.views.abstract')

class MatchWaitPage(abstract.MatchCheckpoint):

    def body_text(self):
        return super(MatchWaitPage, self).body_text()

    def title_text(self):
        return super(MatchWaitPage, self).title_text()

    def action(self):
        return super(MatchWaitPage, self).action()

class SubsessionWaitPage(abstract.SubsessionCheckpoint):

    def body_text(self):
        return super(SubsessionWaitPage, self).body_text()

    def title_text(self):
        return super(SubsessionWaitPage, self).title_text()

    def action(self):
        return super(SubsessionWaitPage, self).action()

class Page(abstract.ParticipantUpdateView):

    def variables_for_template(self):
        return super(Page, self).variables_for_template()

    def after_valid_form_submission(self):
        return super(Page, self).after_valid_form_submission()

    def get_form_class(self):
        return super(Page, self).get_form_class()

    def participate_condition(self):
        return super(Page, self).participate_condition()

    template_name = None

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