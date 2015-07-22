# -*- coding: utf-8 -*-

import easymoney

from django.utils.encoding import force_text

import floppyforms.__future__ as forms
import floppyforms.widgets

import otree.forms
import otree.widgets
from .base import TestCase


class BasicWidgetTests(TestCase):
    def test_all_widgets_are_available(self):
        for widget_name in floppyforms.widgets.__all__:
            self.assertTrue(hasattr(otree.widgets, widget_name),
                            'otree.widgets is missing the widget {0}'.format(
                                widget_name))

    def test_attrs_yield_form_control_class(self):
        class Form(otree.forms.Form):
            first_name = otree.forms.CharField()

        rendered = force_text(Form()['first_name'])
        elem = (
            '<input type="text" name="first_name" '
            'required class="form-control" id="id_first_name" />'
        )
        self.assertHTMLEqual(rendered, elem)


class CheckboxSelectMultipleHorizontalTests(TestCase):
    maxDiff = None

    class CheckboxForm(forms.Form):
        numbers = forms.MultipleChoiceField(choices=(
            ('1', '1'),
            ('2', '2'),
            ('3', '3'),
        ), widget=otree.forms.CheckboxSelectMultipleHorizontal)

    def test_widget(self):
        form = self.CheckboxForm()

        rendered = force_text(form['numbers'])
        self.assertHTMLEqual(
            rendered,
            """
            <label class="checkbox-inline" for="id_numbers_1">
                <input type="checkbox" id="id_numbers_1" name="numbers"
                    value="1" /> 1
            </label>
            <label class="checkbox-inline" for="id_numbers_2">
                <input type="checkbox" id="id_numbers_2" name="numbers"
                    value="2" /> 2
            </label>
            <label class="checkbox-inline" for="id_numbers_3">
                <input type="checkbox" id="id_numbers_3" name="numbers"
                    value="3" /> 3
            </label>
            """)


class CurrencyInputTests(TestCase):
    maxDiff = None

    class CurrencyForm(forms.Form):
        currency = otree.forms.CurrencyField()

    def test_widget(self):
        form = self.CurrencyForm({'currency': easymoney.Money('52.23')})
        rendered = force_text(form['currency'])

        self.assertTrue(
            u'''<span class="input-group-addon">€</span>''' in rendered)
        # Make sure that the value does not contain the currency symbol
        self.assertTrue('''value="52.23"''' in rendered)


class RadioSelectHorizontalTests(TestCase):
    maxDiff = None

    class RadioForm(forms.Form):
        numbers = forms.ChoiceField(choices=(
            ('1', '1'),
            ('2', '2'),
            ('3', '3'),
        ), widget=otree.forms.RadioSelectHorizontal)

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
