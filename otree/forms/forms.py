#!/usr/bin/env python
# -*- coding: utf-8 -*-

import copy
from decimal import Decimal

import floppyforms.__future__ as forms
from floppyforms.__future__.models import (
    FORMFIELD_OVERRIDES as FLOPPYFORMS_FORMFIELD_OVERRIDES
)
from floppyforms.__future__.models import (
    ModelFormMetaclass as FloppyformsModelFormMetaclass
)

import django.forms as django_forms
from django.forms import models as django_model_forms
from django.utils.translation import ugettext as _


import easymoney

import otree.common_internal
import otree.models.session
import otree.constants
from otree.forms import fields
from otree.db import models


__all__ = (
    'formfield_callback', 'modelform_factory', 'BaseModelForm', 'ModelForm'
)


FORMFIELD_OVERRIDES = FLOPPYFORMS_FORMFIELD_OVERRIDES.copy()

FORMFIELD_OVERRIDES.update({
    # Overrides from fields defined in otree.db.models

    models.NullBooleanField: {
        'form_class': forms.NullBooleanField,
        'choices_form_class': forms.TypedChoiceField},
    models.BigIntegerField: {
        'form_class': forms.IntegerField,
        'choices_form_class': forms.TypedChoiceField},
    # Binary field is never editable, so we don't need to convert it.
    models.BooleanField: {
        'form_class': forms.BooleanField,
        'choices_form_class': forms.TypedChoiceField},
    models.CharField: {
        'form_class': forms.CharField,
        'choices_form_class': forms.TypedChoiceField},
    models.CommaSeparatedIntegerField: {
        'form_class': forms.CharField,
        'choices_form_class': forms.TypedChoiceField},
    models.DateField: {
        'form_class': forms.DateField,
        'choices_form_class': forms.TypedChoiceField},
    models.DateTimeField: {
        'form_class': forms.DateTimeField,
        'choices_form_class': forms.TypedChoiceField},
    models.DecimalField: {
        'form_class': forms.DecimalField,
        'choices_form_class': forms.TypedChoiceField},
    models.EmailField: {
        'form_class': forms.EmailField,
        'choices_form_class': forms.TypedChoiceField},
    models.FileField: {
        'form_class': forms.FileField,
        'choices_form_class': forms.TypedChoiceField},
    models.FilePathField: {
        'form_class': forms.FilePathField,
        'choices_form_class': forms.TypedChoiceField},
    models.FloatField: {
        'form_class': forms.FloatField,
        'choices_form_class': forms.TypedChoiceField},
    models.IntegerField: {
        'form_class': forms.IntegerField,
        'choices_form_class': forms.TypedChoiceField},
    models.IPAddressField: {
        'form_class': forms.IPAddressField,
        'choices_form_class': forms.TypedChoiceField},
    models.GenericIPAddressField: {
        'form_class': forms.GenericIPAddressField,
        'choices_form_class': forms.TypedChoiceField},
    models.PositiveIntegerField: {
        'form_class': forms.IntegerField,
        'choices_form_class': forms.TypedChoiceField},
    models.PositiveSmallIntegerField: {
        'form_class': forms.IntegerField,
        'choices_form_class': forms.TypedChoiceField},
    models.SlugField: {
        'form_class': forms.SlugField,
        'choices_form_class': forms.TypedChoiceField},
    models.SmallIntegerField: {
        'form_class': forms.IntegerField,
        'choices_form_class': forms.TypedChoiceField},
    models.TextField: {
        'form_class': forms.CharField,
        'widget': forms.Textarea,
        'choices_form_class': forms.TypedChoiceField},
    models.TimeField: {
        'form_class': forms.TimeField,
        'choices_form_class': forms.TypedChoiceField},
    models.URLField: {
        'form_class': forms.URLField,
        'choices_form_class': forms.TypedChoiceField},
    models.ManyToManyField: {
        'form_class': forms.ModelMultipleChoiceField,
        'choices_form_class': forms.TypedChoiceField},
    models.OneToOneField: {
        'form_class': forms.ModelChoiceField,
        'choices_form_class': forms.TypedChoiceField},

    # Other custom db fields used in otree.

    models.RandomCharField: {
        'form_class': forms.CharField,
        'choices_form_class': forms.TypedChoiceField},

    models.CurrencyField: {
        'form_class': fields.CurrencyField,
        'choices_form_class': fields.CurrencyChoiceField},
})


def formfield_callback(db_field, **kwargs):
    defaults = FORMFIELD_OVERRIDES.get(db_field.__class__, {}).copy()
    # Take the `widget` attribute into account that might be set for a db
    # field. We want to override the widget given by FORMFIELD_OVERRIDES.
    widget = getattr(db_field, 'widget', None)
    if widget:
        defaults['widget'] = widget
    defaults.update(kwargs)
    return db_field.formfield(**defaults)


def modelform_factory(*args, **kwargs):
    """
    This custom modelform_factory must be used in all places instead of the
    default django implemention in order to use the correct
    `formfield_callback` function.

    Otherwise the created modelform will not use the floppyfied fields defined
    in FORMFIELD_OVERRIDES.
    """
    kwargs.setdefault('formfield_callback', formfield_callback)
    return django_model_forms.modelform_factory(*args, **kwargs)


class BaseModelFormMetaclass(FloppyformsModelFormMetaclass):
    """
    Metaclass for BaseModelForm in order to inject our custom implementation of
    `formfield_callback`.
    """
    def __new__(mcs, name, bases, attrs):
        if 'formfield_callback' not in attrs:
            attrs['formfield_callback'] = formfield_callback
        return super(BaseModelFormMetaclass, mcs).__new__(
            mcs, name, bases, attrs)


class BaseModelForm(forms.ModelForm):
    __metaclass__ = BaseModelFormMetaclass

    def __init__(self, *args, **kwargs):
        """Special handling for 'choices' argument, NullBooleanFields, and
        initial choice: If the user explicitly specifies a None choice
        (which is usually  rendered as '---------'), we should always respect
        it

        Otherwise:
        If the field is a NullBooleanField:
            if it's rendered as a Select menu (which it is by default), it
            should have a None choice
        If the field is a RadioSelect:
            it should not have a None choice
            If the DB field's value is None and the user did not specify an
            inital value, nothing should be selected by default.
            This will conceptually match a dropdown.

        """

        super(BaseModelForm, self).__init__(*args, **kwargs)

        for field_name in self.fields:
            if hasattr(self.instance, '%s_choices' % field_name):
                choices = getattr(self.instance, '%s_choices' % field_name)()
                choices = otree.common_internal.expand_choice_tuples(choices)

                model_field = self.instance._meta.get_field(field_name)
                model_field_copy = copy.copy(model_field)
                model_field_copy._choices = choices

                self.fields[field_name] = formfield_callback(model_field_copy)
            if hasattr(self.instance, '%s_label' % field_name):
                self.fields[field_name].label = getattr(
                    self.instance, '%s_label' % field_name
                )()

        for field_name in self.fields:
            field = self.fields[field_name]
            if isinstance(field.widget, forms.RadioSelect):
                # Fields with a RadioSelect should be rendered without the
                # '---------' option, and with nothing selected by default, to
                # match dropdowns conceptually, and because the '---------' is
                # not necessary if no item is selected initially. if the
                # selected item was the None choice, by removing it, nothing
                # is selected.

                if field.choices[0][0] in {u'', None}:
                    field.choices = field.choices[1:]

        self._setup_field_boundaries()

    def _get_field_boundaries(self, field_name):
        """
        Get the field boundaries from a method defined on the model.

        Example (will get boundaries from `amount_bounds`):

            class MyModel(...):
                amount = models.IntegerField()

                def amount_bounds(self):
                    return [1, 5]

        If the method is not found, it will return ``(None, None)``.
        """
        method_name = '%s_bounds' % field_name
        if hasattr(self.instance, method_name):
            method = getattr(self.instance, method_name)
            return method()
        model_field = self.instance._meta.get_field_by_name(field_name)[0]
        return getattr(model_field, 'bounds', None) or [None, None]

    def _setup_field_boundaries(self):
        for field_name, field in self.fields.items():
            # We want to support both, django and floppyforms widgets.
            cond = isinstance(
                field.widget, (django_forms.NumberInput, forms.NumberInput)
            )
            if cond:
                min_bound, max_bound = self._get_field_boundaries(field_name)
                if isinstance(min_bound, easymoney.Money):
                    min_bound = Decimal(min_bound)
                if isinstance(max_bound, easymoney.Money):
                    max_bound = Decimal(max_bound)
                if min_bound is not None:
                    field.widget.attrs['min'] = min_bound
                if max_bound is not None:
                    field.widget.attrs['max'] = max_bound
                # is this UI too intrusive?
                # if min_bound is not None and max_bound is not None:
                #    field.widget.attrs['placeholder'] = '({} - {})'.format(
                #        min_bound, max_bound
                #    )

    def null_boolean_field_names(self):
        null_boolean_fields_in_model = [
            field.name for field in self.Meta.model._meta.fields
            if isinstance(field, models.NullBooleanField)
        ]
        return [field_name for field_name in self.fields
                if field_name in null_boolean_fields_in_model]

    def _clean_fields(self):
        null_boolean_field_names = self.null_boolean_field_names()
        for name, field in self.fields.items():
            # value_from_datadict() gets the data from the data dictionaries.
            # Each widget type knows how to retrieve its own data, because some
            # widgets split data over several HTML fields.
            value = field.widget.value_from_datadict(
                self.data, self.files, self.add_prefix(name)
            )
            try:
                if isinstance(field, forms.FileField):
                    initial = self.initial.get(name, field.initial)
                    value = field.clean(value, initial)
                else:
                    value = field.clean(value)
                self.cleaned_data[name] = value
                if name in null_boolean_field_names and value is None:
                    msg = _('This field is required.')
                    raise forms.ValidationError(msg)
                if hasattr(self.instance, '%s_bounds' % name):
                    lower, upper = getattr(self.instance, '%s_bounds' % name)()
                    if not lower <= value <= upper:
                        msg = 'Must be between {} and {}, inclusive.'
                        raise forms.ValidationError(msg.format(lower, upper))
                if hasattr(self.instance, '%s_error_message' % name):
                    error_string = getattr(
                        self.instance, '%s_error_message' % name
                    )(value)
                    if error_string:
                        raise forms.ValidationError(error_string)
                if hasattr(self, 'clean_%s' % name):
                    value = getattr(self, 'clean_%s' % name)()
                    self.cleaned_data[name] = value
            except forms.ValidationError as e:
                self.add_error(name, e)


class ModelForm(BaseModelForm):
    pass
