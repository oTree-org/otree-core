# -*- coding: utf-8 -*-
import ptree.views
import ptree.views.concrete
import {{ app_name }}.forms as forms
from {{ app_name }}.utilities import ParticipantMixin, ExperimenterMixin
from django.utils.translation import ugettext as _
from django.conf import settings
from ptree.common import currency

class Initialize(ParticipantMixin, ptree.views.Initialize):
    pass

class InitializeExperimenter(ExperimenterMixin, ptree.views.InitializeExperimenter):
    pass

class MyPage(ParticipantMixin, ptree.views.Page):

    template_name = '{{ app_name }}/MyView.html'

    def get_form_class(self):
        return forms.MyForm

    def show_skip_wait(self):
        return self.PageActions.show

    def variables_for_template(self):
        return {}

    def after_valid_form_submission(self):
        """If all you need to do is save the form to the database,
        this can be left blank or omitted."""

class ExperimenterPage(ExperimenterMixin, ptree.views.ExperimenterPage):

    pass
