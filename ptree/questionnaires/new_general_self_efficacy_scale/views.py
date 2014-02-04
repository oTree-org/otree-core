import ptree.views.abstract
import ptree.questionnaires.new_general_self_efficacy_scale.forms as forms

class ViewInThisApp(object):
    name_in_url = 'NGES'

class LifeOrientationTest(ptree.views.abstract.CreateView, ViewInThisApp):
    form_class = forms.NewGeneralSelfEfficacyScaleForm
    template_name = 'life_orientation_test/Questionnaire.html'