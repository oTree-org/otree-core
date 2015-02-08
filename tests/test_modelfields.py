from django.test import TestCase
import otree.forms

from .models import SimpleModel, FormFieldModel


class TestModelForm(otree.forms.ModelForm):
    class Meta:
        model = FormFieldModel
        exclude = ()


class WidgetArgumentTests(TestCase):

    def test_widget_argument(self):
        self.assertIsInstance(
            TestModelForm.base_fields['char'].widget, otree.forms.TextInput
        )
        self.assertIsInstance(
            TestModelForm.base_fields['alt_date_time'].widget,
            otree.forms.SplitDateTimeWidget
        )
        self.assertIsInstance(
            TestModelForm.base_fields['text'].widget, otree.forms.Textarea
        )
        self.assertIsInstance(
            TestModelForm.base_fields['alt_text'].widget,
            otree.forms.TextInput
        )


class ModelTests(TestCase):

    def test_get_FIELD_display(self):
        obj = SimpleModel(name='bob')
        self.assertEqual(obj.get_name_display(), 'BOB')
