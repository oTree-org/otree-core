import ptree.views.abstract
import ptree.questionnaires.life_orientation_test.forms as forms

class InThisApp(object):
    name_in_url = 'LOT_R'

class LifeOrientationTest(ptree.views.abstract.ParticipantCreateView, InThisApp):
    form_class = forms.LifeOrientationTestForm
    template_name = 'life_orientation_test/Questionnaire.html'