from decimal import Decimal
from django.test import TestCase
import otree.forms

from .models import BoundFieldModel, SimpleModel, FormFieldModel


class TestModelForm(otree.forms.ModelForm):
    class Meta:
        model = FormFieldModel
        exclude = ()


class BoundFieldModelForm(otree.forms.ModelForm):
    class Meta:
        model = BoundFieldModel
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


class FieldBoundTests(TestCase):

    def test_big_integer_bounds(self):
        form = BoundFieldModelForm()
        self.assertEqual(form.fields['big_integer'].widget.attrs['min'], 0)
        self.assertEqual(
            form.fields['big_integer'].widget.attrs['max'], 10 ** 10
        )
        self.assertTrue('min="0"' in str(form['big_integer']))
        self.assertTrue('max="10000000000"' in str(form['big_integer']))

    def test_currency_bounds(self):
        form = BoundFieldModelForm()
        self.assertEqual(form.fields['currency'].widget.attrs['min'], 0)
        self.assertEqual(form.fields['currency'].widget.attrs['max'], 0.5)
        self.assertTrue('min="0"' in str(form['currency']))
        self.assertTrue('max="0.5"' in str(form['currency']))

    def test_decimal_bounds(self):
        form = BoundFieldModelForm()
        one_third = Decimal('1') / Decimal('3')
        self.assertEqual(form.fields['decimal'].widget.attrs['min'], 0.111)
        self.assertEqual(form.fields['decimal'].widget.attrs['max'], one_third)
        self.assertTrue('min="0.111"' in str(form['decimal']))
        # The threes might continue, so we don't check for a quote.
        self.assertTrue('max="0.33333333333333333333' in str(form['decimal']))

    def test_integer_bounds(self):
        form = BoundFieldModelForm()
        self.assertEqual(form.fields['integer'].widget.attrs['min'], -5)
        self.assertEqual(form.fields['integer'].widget.attrs['max'], 9999)
        self.assertTrue('min="-5"' in str(form['integer']))
        self.assertTrue('max="9999"' in str(form['integer']))

    def test_integer_no_bounds_bounds(self):
        form = BoundFieldModelForm()
        self.assertEqual(
            form.fields['integer_no_bounds'].widget.attrs.get('min'), None
        )
        self.assertEqual(
            form.fields['integer_no_bounds'].widget.attrs.get(max), None
        )
        self.assertTrue('min="' not in str(form['integer_no_bounds']))
        self.assertTrue('max="' not in str(form['integer_no_bounds']))

    def test_positive_integer_bounds(self):
        form = BoundFieldModelForm()
        self.assertEqual(
            form.fields['positive_integer'].widget.attrs['min'], 0
        )
        self.assertEqual(
            form.fields['positive_integer'].widget.attrs['max'], 10
        )
        self.assertTrue('min="0"' in str(form['positive_integer']))
        self.assertTrue('max="10"' in str(form['positive_integer']))

    def test_small_integer_bounds(self):
        form = BoundFieldModelForm()
        self.assertEqual(form.fields['small_integer'].widget.attrs['min'], -1)
        self.assertEqual(form.fields['small_integer'].widget.attrs['max'], 1)
        self.assertTrue('min="-1"' in str(form['small_integer']))
        self.assertTrue('max="1"' in str(form['small_integer']))

    def test_small_positive_integer_bounds(self):
        form = BoundFieldModelForm()
        self.assertEqual(
            form.fields['small_positive_integer'].widget.attrs['min'], 0
        )
        self.assertEqual(
            form.fields['small_positive_integer'].widget.attrs['max'], 1
        )
        self.assertTrue('min="0"' in str(form['small_positive_integer']))
        self.assertTrue('max="1"' in str(form['small_positive_integer']))

    def test_dependent_on_instance(self):
        instance = BoundFieldModel()
        instance.upper_bound = 1234
        form = BoundFieldModelForm(instance=instance)
        self.assertEqual(form.fields['integer'].widget.attrs['min'], -5)
        self.assertEqual(form.fields['integer'].widget.attrs['max'], 1234)
