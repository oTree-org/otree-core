#!/usr/bin/env python
# -*- coding: utf-8 -*-

import otree.forms

from .base import TestCase
from .models import CurrencyFieldTestModel
from .models import SimpleModel
from .models import FormFieldModel


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


class CurrencyFieldTests(TestCase):
    def test_default_value_zero_in_modelform(self):
        # Make sure that a value of 0.00 is included in rendered output. It is
        # a falsy value if it's a Decimal instance. So this might fail if the
        # value is not converted to string prior to rendering in the form. See
        # https://github.com/oTree-org/otree-core/issues/326

        class CurrencyFieldTestModelForm(otree.forms.ModelForm):
            class Meta:
                model = CurrencyFieldTestModel
                exclude = ()

        form = CurrencyFieldTestModelForm()
        rendered = str(form['currency_with_default_value_zero'])
        self.assertTrue('value="0.00"' in rendered)
