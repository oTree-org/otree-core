from django.test import TestCase
import otree.forms_internal
import otree.widgets

from .models import FormFieldModel


class TestModelForm(otree.forms_internal.BaseModelForm):
    class Meta:
        model = FormFieldModel
        exclude = ()


class WidgetArgumentTests(TestCase):
    def test_widget_argument(self):
        self.assertEqual(TestModelForm.base_fields['char'].widget.__class__, otree.widgets.TextInput)
        self.assertEqual(TestModelForm.base_fields['alt_date_time'].widget.__class__, otree.widgets.SplitDateTimeWidget)
        self.assertEqual(TestModelForm.base_fields['text'].widget.__class__, otree.widgets.Textarea)
        self.assertEqual(TestModelForm.base_fields['alt_text'].widget.__class__, otree.widgets.TextInput)
