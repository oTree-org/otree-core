import ptree.views.abstract
import ptree.questionnaires.new_general_self_efficacy_scale.forms as forms

class ViewInThisApp(object):
    url_base = 'NGES'

class LifeOrientationTest(ptree.views.abstract.CreateView, ViewInThisApp):
    form_class = forms.NewGeneralSelfEfficacyScaleForm
    template_name = 'life_orientation_test/Questionnaire.html'