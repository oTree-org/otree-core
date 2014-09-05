import floppyforms.__future__ as forms
from django.utils.translation import ugettext as _
import copy
import otree.common
import otree.models.common
import otree.sessionlib.models
import otree.constants
from otree.db import models
import easymoney


#FIXME: port these to floppyforms
'''
class FormHelper(crispy_forms.helper.FormHelper):
    def __init__(self, *args, **kwargs):
        super(FormHelper, self).__init__(*args, **kwargs)
        self.form_id = otree.constants.form_element_id
        self.form_class = 'form'
        self.add_input(Submit('submit',
                     _('Next'), #TODO: make this customizable
                     css_class='btn-large btn-primary'))
'''

class BaseModelForm(forms.ModelForm):

    def defaults(self):
        """Return a dict of any initial values"""
        return {}

    def choices(self):
        return {}

    def labels(self):
        return {}


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
        kwargs.setdefault('initial', {}).update(self.defaults())
        super(BaseModelForm, self).__init__(*args, **kwargs)

        for field_name in self.fields:
            if hasattr(self.instance, '%s_choices' % field_name):
                choices = getattr(self.instance, '%s_choices' % field_name)()
                choices = otree.common.expand_choice_tuples(choices)

                model_field = self.instance._meta.get_field(field_name)
                model_field_copy = copy.copy(model_field)
                model_field_copy._choices = choices

                self.fields[field_name] = model_field_copy.formfield()

        for field_name, label in self.labels().items():
            self.fields[field_name].label = label

        for field_name in self.fields:
            field = self.fields[field_name]
            if isinstance(field.widget, forms.RadioSelect):
                # Fields with a RadioSelect should be rendered without the '---------' option,
                # and with nothing selected by default, to match dropdowns conceptually.
                # if the selected item was the None choice, by removing it, nothing is selected.

                if field.choices[0][0] in {u'', None}:
                    field.choices = field.choices[1:]


    def null_boolean_field_names(self):
        null_boolean_fields_in_model = [field.name for field in self.Meta.model._meta.fields if isinstance(field, models.NullBooleanField)]
        return [field_name for field_name in self.fields if field_name in null_boolean_fields_in_model]

    def clean(self):
        """
        2/17/2014: why don't i do this in the model field definition
        maybe because None is not a valid value for a submitted value,
        but it's OK for an initial value
        """
        cleaned_data = super(BaseModelForm, self).clean()
        for field_name in self.null_boolean_field_names():
            if cleaned_data[field_name] == None:
                msg = _('This field is required.')
                self._errors[field_name] = self.error_class([msg])
        return cleaned_data

    def _clean_fields(self):
        """2014/3/28: this method is copied from django ModelForm source code. I am adding a validate_%s method that is a bit
        simpler than clean_%s"""
        for name, field in self.fields.items():
            # value_from_datadict() gets the data from the data dictionaries.
            # Each widget type knows how to retrieve its own data, because some
            # widgets split data over several HTML fields.
            value = field.widget.value_from_datadict(self.data, self.files, self.add_prefix(name))
            try:
                if isinstance(field, forms.FileField):
                    initial = self.initial.get(name, field.initial)
                    value = field.clean(value, initial)
                else:
                    value = field.clean(value)
                self.cleaned_data[name] = value
                if hasattr(self.instance, '%s_error_message' % name):
                    error_string = getattr(self.instance, '%s_error_message' % name)(value)
                    if error_string:
                        self._errors[name] = self.error_class([error_string])
                        if name in self.cleaned_data:
                            del self.cleaned_data[name]
                if hasattr(self, 'clean_%s' % name):
                    value = getattr(self, 'clean_%s' % name)()
                    self.cleaned_data[name] = value

            except forms.ValidationError as e:
                self._errors[name] = self.error_class(e.messages)
                if name in self.cleaned_data:
                    del self.cleaned_data[name]

