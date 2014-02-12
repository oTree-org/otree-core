from django import forms
from django.utils.translation import ugettext as _
import crispy_forms.helper
from crispy_forms.layout import Submit

import ptree.common
import ptree.models.common
import ptree.sessionlib.models
import ptree.constants
from ptree.db import models


DEFAULT_NULLBOOLEAN_CHOICES = ((None, '---------'),
                               (True, _('Yes')),
                               (False, _('No')))

class FormHelper(crispy_forms.helper.FormHelper):
    def __init__(self, *args, **kwargs):
        super(FormHelper, self).__init__(*args, **kwargs)
        self.form_id = ptree.constants.form_element_id
        self.form_class = 'form'
        self.add_input(Submit('submit',
                     _('Next'), #TODO: make this customizable
                     css_class='btn-large btn-primary'))



class BaseModelForm(forms.ModelForm):

    def field_initial_values(self):
        """Return a dict of any initial values"""
        return {}

    def field_choices(self):
        return {}

    def field_labels(self):
        return {}

    def currency_choices(self, amounts):
        return [(None, '---------')] + [(amount, ptree.common.currency(amount)) for amount in amounts]

    def layout(self):
        """Child classes can override this to customize form layout using crispy-forms"""
        return None

    def __init__(self, *args, **kwargs):
        """
        Special handling for 'choices' argument, NullBooleanFields, and initial choice:
        If the user explicitly specifies a None choice (which is usually rendered as '---------', we should always respect it

        Otherwise:
        If the field is a NullBooleanField:
            if it's rendered as a Select menu (which it is by default), it should have a None choice
        If the field is a RadioSelect:
            it should not have a None choice
            If the DB field's value is None and the user did not specify an inital value, nothing should be selected by default.
            This will conceptually match a dropdown.
        """
        self.process_kwargs(kwargs)
        initial = kwargs.get('initial', {})
        initial.update(self.field_initial_values())
        kwargs['initial'] = initial

        super(BaseModelForm, self).__init__(*args, **kwargs)

        for field_name, label in self.field_labels().items():
            self.fields[field_name].label = label

        # allow a user to set field_choices without having to remember to set the widget to Select.
        # why don't we just make the user explicitly set the form widget in Meta?
        # that would make the problem
        for field_name, choices in self.field_choices().items():
            field = self.fields[field_name]

            try:
                # the following line has no effect.
                # it's just a test whether this field's widget can accept a choices arg.
                # otherwise, setting field.choices will have no effect.
                field.widget.__class__(choices=choices)
            except TypeError:
                # if the current widget can't accept a choices arg, fall back to using a Select widget
                # FIXME: what if there are additional args to the constructor?
                field.widget = forms.Select(choices=choices)
            else:
                field.choices = choices

        for field_name in self.fields:
            field = self.fields[field_name]
            if isinstance(field.widget, forms.RadioSelect):
                # Fields with a RadioSelect should be rendered without the '---------' option,
                # and with nothing selected by default, to match dropdowns conceptually.
                # if the selected item was the None choice, by removing it, nothing is selected.
                if field.choices[0][0] in {u'', None}:
                    field.choices = field.choices[1:]

        # crispy forms
        self.helper = FormHelper()
        self.helper.layout = self.layout()

    def null_boolean_field_names(self):
        null_boolean_fields_in_model = [field.name for field in self.Meta.model._meta.fields if isinstance(field, models.NullBooleanField)]
        return [field_name for field_name in self.fields if field_name in null_boolean_fields_in_model]

    def clean(self):
        cleaned_data = super(BaseModelForm, self).clean()
        for field_name in self.null_boolean_field_names():
            if cleaned_data[field_name] == None:
                msg = _('This field is required.')
                self._errors[field_name] = self.error_class([msg])
        return cleaned_data

class ModelForm(BaseModelForm):
    """i.e. participant modelform."""

    def process_kwargs(self, kwargs):
        self.participant = kwargs.pop('participant')
        self.match = kwargs.pop('match')
        self.treatment = kwargs.pop('treatment')
        self.experiment = kwargs.pop('experiment')
        self.request = kwargs.pop('request')
        self.session = kwargs.pop('session')
        self.time_limit_was_exceeded = kwargs.pop('time_limit_was_exceeded')

class ExperimenterModelForm(BaseModelForm):
    def process_kwargs(self, kwargs):
        self.experiment = kwargs.pop('experiment')
        self.request = kwargs.pop('request')
        self.session = kwargs.pop('session')

class StubModelForm(ModelForm):
    class Meta:
        model = ptree.sessionlib.models.StubModel
        fields = []

class ExperimenterStubModelForm(ExperimenterModelForm):
    class Meta:
        model = ptree.sessionlib.models.StubModel
        fields = []
