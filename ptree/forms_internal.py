from django import forms
from django.utils.translation import ugettext as _
import crispy_forms.helper
from crispy_forms.layout import Submit, Layout, Fieldset
import copy
import ptree.common
import ptree.models.common
import ptree.sessionlib.models
import ptree.constants
from ptree.db import models
import easymoney

class FormHelper(crispy_forms.helper.FormHelper):
    def __init__(self, *args, **kwargs):
        super(FormHelper, self).__init__(*args, **kwargs)
        self.form_id = ptree.constants.form_element_id
        self.form_class = 'form'
        self.add_input(Submit('submit',
                     _('Next'), #TODO: make this customizable
                     css_class='btn-large btn-primary'))


class BaseModelForm(forms.ModelForm):

    def layout(self):
        """Child classes can override this to customize form layout using crispy-forms"""
        order = self.order()

        if order:
            return Layout(
                Fieldset(
                    '',
                    *order
                )
            )

    def initial_values(self):
        """Return a dict of any initial values"""
        return {}

    def choices(self):
        return {}

    def labels(self):
        return {}

    def order(self):
        pass


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
        kwargs.setdefault('initial', {}).update(self.initial_values())
        super(BaseModelForm, self).__init__(*args, **kwargs)


        # allow a user to set field_choices without having to remember to set the widget to Select.
        # why don't we just make the user explicitly set the form widget in Meta?
        # that would make the problem
        for field_name, choices in self.choices().items():
            choices = ptree.common.expand_choice_tuples(choices)
            field = self.fields[field_name]

            model_field = self.instance._meta.get_field(field_name)
            model_field_copy = copy.copy(model_field)
            model_field_copy._choices = choices

            try:
                widget = self._meta.widgets.get(field_name)
            except AttributeError:
                widget = None
            if isinstance(model_field, models.MoneyField):
                if isinstance(widget, forms.RadioSelect):
                    widget.__class__ = easymoney.MoneyRadioSelect
                if isinstance(widget, forms.Select):
                    widget.__class__ = easymoney.MoneySelect

            self.fields[field_name] = model_field_copy.formfield(widget=widget)


        for field_name, label in self.labels().items():
            self.fields[field_name].label = label

        # crispy forms
        self.helper = FormHelper()
        self.helper.layout = self.layout()

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
                if hasattr(self, '%s_error_message' % name):
                    error_string = getattr(self, '%s_error_message' % name)(value)
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

class ParticipantModelForm(BaseModelForm):
    """i.e. participant modelform."""

    def process_kwargs(self, kwargs):
        self.participant = kwargs.pop('participant')
        self.match = kwargs.pop('match')
        self.treatment = kwargs.pop('treatment')
        self.subsession = kwargs.pop('subsession')
        self.request = kwargs.pop('request')
        self.session = kwargs.pop('session')
        self.time_limit_was_exceeded = kwargs.pop('time_limit_was_exceeded')

class ExperimenterModelForm(BaseModelForm):
    def process_kwargs(self, kwargs):
        self.subsession = kwargs.pop('subsession')
        self.request = kwargs.pop('request')
        self.session = kwargs.pop('session')
        self.time_limit_was_exceeded = kwargs.pop('time_limit_was_exceeded')

class StubModelForm(ParticipantModelForm):
    class Meta:
        model = ptree.sessionlib.models.StubModel
        fields = []

class ExperimenterStubModelForm(ExperimenterModelForm):
    class Meta:
        model = ptree.sessionlib.models.StubModel
        fields = []

