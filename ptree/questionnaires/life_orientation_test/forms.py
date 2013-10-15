from ptree.forms import ModelForm
from ptree.questionnaires.life_orientation_test.models import LifeOrientationTest

class LifeOrientationTestForm(ModelForm):
    class Meta:
        model = LifeOrientationTest
        # is it possible to get rid of these? maybe i should add that stuff back into the questionnaire.
        exclude = ['object_id', 'content_type']


