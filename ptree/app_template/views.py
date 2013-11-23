import ptree.views
import ptree.views.concrete
import {{ app_name }}.forms as forms
from {{ app_name }}.utilities import ViewInThisApp
from django.utils.translation import ugettext as _
from django.conf import settings

class GetTreatmentOrParticipant(ViewInThisApp, ptree.views.GetTreatmentOrParticipant):
    pass

class StartTreatment(ViewInThisApp, ptree.views.StartTreatment):
    template_name = 'Start.html'
    form_class = forms.StartForm

# change the name as necessary
class MyView(ViewInThisApp, ptree.views.UpdateView):

    form_class = {{ app_name }}.forms.MyForm
    template_name = '{{ app_name }}/MyView.html'

    def show_skip_wait(self):
        return self.PageActions.show

    def variables_for_template(self):
        return {}

    def after_valid_form_submission(self):
        """If all you need to do is save the form to the database,
        this can be left blank or omitted."""

class RedemptionCode(ViewInThisApp, ptree.views.UpdateView):
    template_name = 'RedemptionCode.html'

    def variables_for_template(self):
        return {'redemption_code': self.participant.code,
                'base_pay': self.treatment.base_pay,
                'bonus': self.participant.bonus(),
                'total_pay': self.participant.total_pay()}