import ptree.views
import ptree.views.concrete
import {{ app_name }}.forms as forms
from {{ app_name }}.utilities import ViewInThisApp
from django.utils.translation import ugettext as _
from django.conf import settings
from ptree.common import currency

class Initialize(ViewInThisApp, ptree.views.Initialize):
    pass

class MyView(ViewInThisApp, ptree.views.UpdateView):

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