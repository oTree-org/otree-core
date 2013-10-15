import ptree.views.abstract
from ptree.questionnaires.life_orientation_test.forms import LifeOrientationTestForm

class ViewInThisApp(object):
    url_base = 'LOT_R'

class LifeOrientationTest(ptree.views.abstract.CreateView, ViewInThisApp):
    form_class = LifeOrientationTestForm
    template_name = 'life_orientation_test/Questionnaire.html'