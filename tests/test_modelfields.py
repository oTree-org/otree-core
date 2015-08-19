#!/usr/bin/env python
# -*- coding: utf-8 -*-

import json

from six.moves import cPickle as pickle

from otree.db import models
import otree.forms

from .base import TestCase
from .models import CurrencyFieldTestModel, SimpleModel, FormFieldModel


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


class JSONPickleFieldTests(TestCase):

    def setUp(self):
        self.test_values = [
            1, 1.33,
            None,
            [1, 2, 3., {}, ["coso", None, {}]],
            {"foo": [], "algo": None, "spam": [1, 2, 3.]},
            [],
            {},
        ]

    def test_json_field(self):
        for value in self.test_values:
            field = models.JSONField(value)
            serialized = field.get_prep_value(value)
            if value is None:
                self.assertIsNone(serialized)
            else:
                self.assertJSONEqual(json.dumps(value), serialized)
            restored = field.to_python(serialized)
            self.assertEquals(value, restored)

    def test_pickle_field(self):
        for value in self.test_values:
            field = models.PickleField(value)
            serialized = field.get_prep_value(value)
            if value is None:
                self.assertIsNone(serialized)
            else:
                self.assertEqual(pickle.dumps(value), serialized)
            restored = field.to_python(serialized)
            self.assertEqual(value, restored)
