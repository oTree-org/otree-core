from ptree.forms import ModelForm
from ptree.questionnaires.life_orientation_test.models import LifeOrientationTest

class LifeOrientationTestForm(ModelForm):
    class Meta:
        model = LifeOrientationTest


