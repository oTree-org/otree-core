import copy
from decimal import Decimal

from django import forms
from django.utils.translation import ugettext as _

import otree.common
import otree.constants
import otree.models
from otree.common import ResponseForException
from otree.currency import Currency, RealWorldCurrency
from otree.db import models


class ModelForm(forms.ModelForm):
    def _get_method_from_page_or_model(self, method_name):
        for obj in [self.view, self.instance]:
            if hasattr(obj, method_name):
                meth = getattr(obj, method_name)
                if callable(meth):
                    return meth

    def __init__(self, *args, view=None, **kwargs):
        """Special handling for 'choices' argument, BooleanFields, and
        initial choice: If the user explicitly specifies a None choice
        (which is usually  rendered as '---------'), we should always respect
        it

        Otherwise:
        If the field is a BooleanField:
            if it's rendered as a Select menu (which it is by default), it
            should have a None choice
        If the field is a RadioSelect:
            it should not have a None choice
            If the DB field's value is None and the user did not specify an
            inital value, nothing should be selected by default.
            This will conceptually match a dropdown.

        """
        # first extract the view instance
        self.view = view

        super().__init__(*args, **kwargs)

        for field_name in self.fields:
            field = self.fields[field_name]

            choices_method = self._get_method_from_page_or_model(
                f'{field_name}_choices'
            )

            if choices_method:
                choices = choices_method()
                choices = otree.common.expand_choice_tuples(choices)

                model_field = self.instance._meta.get_field(field_name)
                # this is necessary so we don't modify the field for other players
                model_field_copy = copy.copy(model_field)
                model_field_copy.choices = choices
                field = model_field_copy.formfield()
                self.fields[field_name] = field

            if isinstance(field.widget, forms.RadioSelect):
                # Fields with a RadioSelect should be rendered without the
                # '---------' option, and with nothing selected by default, to
                # match dropdowns conceptually, and because the '---------' is
                # not necessary if no item is selected initially. if the
                # selected item was the None choice, by removing it, nothing
                # is selected.

                # maybe they set the widget to Radio, but forgot to specify
                # choices. that's a mistake, but if oTree validates it, it
                # should do so somewhere else (because this is just for radio)
                # need to also check dropdown menus
                if hasattr(field, 'choices'):
                    choices = field.choices
                    if len(choices) >= 1 and choices[0][0] in {u'', None}:
                        field.choices = choices[1:]

        self._set_min_max_on_widgets()

    def _get_field_bound(self, field_name, min_or_max: str):
        model_field = self.instance._meta.get_field(field_name)

        min_method = self._get_method_from_page_or_model(f'{field_name}_{min_or_max}')
        if min_method:
            return min_method()
        else:
            return getattr(model_field, min_or_max, None)

    def _set_min_max_on_widgets(self):
        for field_name, field in self.fields.items():
            if isinstance(field.widget, forms.NumberInput):
                for min_or_max in ['min', 'max']:
                    bound = self._get_field_bound(field_name, min_or_max)
                    if isinstance(bound, (Currency, RealWorldCurrency)):
                        bound = Decimal(bound)
                    if bound is not None:
                        field.widget.attrs[min_or_max] = bound

    def _clean_fields(self):
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

                model_field = self.instance._meta.get_field(name)
                if (
                    isinstance(model_field, models.BooleanField)
                    and value is None
                    and not model_field.blank
                ):
                    msg = otree.constants.field_required_msg
                    raise forms.ValidationError(msg)

                lower = self._get_field_bound(name, 'min')
                upper = self._get_field_bound(name, 'max')

                # allow blank=True and min/max to be used together
                # the field is optional, but
                # if a value is submitted, it must be within [min,max]
                if value is not None:
                    if lower is not None and value < lower:
                        msg = _('Value must be greater than or equal to {}.')
                        raise forms.ValidationError(msg.format(lower))
                    if upper is not None and value > upper:
                        msg = _('Value must be less than or equal to {}.')
                        raise forms.ValidationError(msg.format(upper))

                error_message_method = self._get_method_from_page_or_model(
                    f'{name}_error_message'
                )
                if error_message_method:
                    try:
                        error_string = error_message_method(value)
                    except:
                        raise ResponseForException
                    if error_string:
                        raise forms.ValidationError(error_string)

            except forms.ValidationError as e:
                self.add_error(name, e)
        if not self.errors and hasattr(self.view, 'error_message'):
            try:
                error_string = self.view.error_message(self.cleaned_data)
            except:
                raise ResponseForException
            if error_string:
                e = forms.ValidationError(error_string)
                self.add_error(None, e)
