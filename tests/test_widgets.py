from django.test import TestCase
from django.utils.encoding import force_text
import floppyforms.__future__ as forms
import floppyforms.widgets

import otree.widgets


class BasicWidgetTests(TestCase):
    def test_all_widgets_are_available(self):
        for widget_name in floppyforms.widgets.__all__:
            self.assertTrue(hasattr(otree.widgets, widget_name),
                            'otree.widgets is missing the widget {0}'.format(
                                widget_name))


class RadioSelectHorizontalTests(TestCase):
    maxDiff = None

    class RadioForm(forms.Form):
        numbers = forms.ChoiceField(choices=(
            ('1', '1'),
            ('2', '2'),
            ('3', '3'),
        ), widget=otree.widgets.RadioSelectHorizontal)

    def test_widget(self):
        form = self.RadioForm()

        rendered = force_text(form['numbers'])
        self.assertHTMLEqual(
            rendered,
            """
            <label class="radio-inline" for="id_numbers_1">
                <input type="radio" id="id_numbers_1" name="numbers"
                    value="1" required /> 1
            </label>
            <label class="radio-inline" for="id_numbers_2">
                <input type="radio" id="id_numbers_2" name="numbers"
                    value="2" required /> 2
            </label>
            <label class="radio-inline" for="id_numbers_3">
                <input type="radio" id="id_numbers_3" name="numbers"
                    value="3" required /> 3
            </label>
            """)
