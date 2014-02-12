import ptree.views.abstract
import ptree.questionnaires.new_general_self_efficacy_scale.forms as forms

class InThisApp(object):
    name_in_url = 'NGES'

class LifeOrientationTest(ptree.views.abstract.ParticipantCreateView, InThisApp):
    form_class = forms.NewGeneralSelfEfficacyScaleForm
    template_name = 'life_orientation_test/Questionnaire.html'