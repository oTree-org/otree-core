"""public api"""

from ptree.views.abstract import (
    InitializeParticipant,
    InitializeExperimenter,
)

from importlib import import_module
abstract = import_module('ptree.views.abstract')

class MatchCheckpoint(abstract.MatchCheckpoint):

    def wait_page_body_text(self):
        return super(MatchCheckpoint, self).wait_page_body_text()

    def wait_page_title_text(self):
        return super(MatchCheckpoint, self).wait_page_title_text()

    def action(self):
        return super(MatchCheckpoint, self).action()

class SubsessionCheckpoint(abstract.SubsessionCheckpoint):

    def wait_page_body_text(self):
        return super(SubsessionCheckpoint, self).wait_page_body_text()

    def wait_page_title_text(self):
        return super(SubsessionCheckpoint, self).wait_page_title_text()

    def action(self):
        return super(SubsessionCheckpoint, self).action()

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