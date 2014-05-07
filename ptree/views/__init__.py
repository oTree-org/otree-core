#

from ptree.views.abstract import (
    #BaseView,
    #ParticipantCreateView,
    #ExperimenterUpdateMultipleView as ExperimenterUpdateMultiplePage,
    InitializeParticipant,
    InitializeExperimenter,
)


from importlib import import_module
abstract = import_module('ptree.views.abstract')

# public API
class Page(abstract.ParticipantUpdateView):

    def variables_for_template(self):
        return super(Page, self).variables_for_template()

    def after_valid_form_submission(self):
        return super(Page, self).after_valid_form_submission()

    def get_form_class(self):
        return super(Page, self).get_form_class()

    def show_skip_wait(self):
        return super(Page, self).show_skip_wait()

    def wait_page_body_text(self):
        return super(Page, self).wait_page_body_text()

    def wait_page_title_text(self):
        return super(Page, self).wait_page_title_text()

    template_name = None

class ExperimenterPage(abstract.ExperimenterUpdateView):

    def variables_for_template(self):
        return super(ExperimenterPage, self).variables_for_template()

    def after_valid_form_submission(self):
        return super(ExperimenterPage, self).after_valid_form_submission()

    def get_form_class(self):
        return super(ExperimenterPage, self).get_form_class()

    def show_skip_wait(self):
        return super(ExperimenterPage, self).show_skip_wait()

    def wait_page_body_text(self):
        return super(ExperimenterPage, self).wait_page_body_text()

    def wait_page_title_text(self):
        return super(ExperimenterPage, self).wait_page_title_text()

    template_name = None

class ExperimenterUpdateMultiplePage(abstract.ExperimenterUpdateMultipleView):

    def variables_for_template(self):
        return super(ExperimenterUpdateMultiplePage, self).variables_for_template()

    def after_valid_form_submission(self):
        return super(ExperimenterUpdateMultiplePage, self).after_valid_form_submission()

    def get_form_class(self):
        return super(ExperimenterUpdateMultiplePage, self).get_form_class()

    def show_skip_wait(self):
        return super(ExperimenterUpdateMultiplePage, self).show_skip_wait()

    def wait_page_body_text(self):
        return super(ExperimenterUpdateMultiplePage, self).wait_page_body_text()

    def wait_page_title_text(self):
        return super(ExperimenterUpdateMultiplePage, self).wait_page_title_text()

    def get_queryset(self):
        return super(ExperimenterUpdateMultiplePage, self).get_queryset()

    template_name = None


