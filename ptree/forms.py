from django import forms
import ptree.common
import ptree.models.common
import ptree.session.models
import ptree.constants
from django.db import models
from django.utils.translation import ugettext as _
import crispy_forms.helper
from crispy_forms.layout import Layout, Fieldset, ButtonHolder, Submit

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

    # In general, pTree does not allow a user to go back and change their answer on a previous page,
    # since that often defeats the purpose of the game (e.g. eliciting an honest answer).
    # But you can put it in rewritable_fields to make it an exception.
    ## UPDATE: deprecated for now
    # rewritable_fields = []

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
        self.process_kwargs(kwargs)
        initial = kwargs.get('initial', {})
        initial.update(self.field_initial_values())
        kwargs['initial'] = initial

        super(BaseModelForm, self).__init__(*args, **kwargs)

        for field_name, label in self.field_labels().items():
            self.fields[field_name].label = label

        for field_name, choices in self.field_choices().items():
            field = self.fields[field_name]

            try:
                # the following line has no effect.
                # it's just a test whether this field's widget can accept a choices arg.
                # otherwise, setting field.choices will have no effect.
                field.widget.__class__(choices=choices)
            except TypeError:
                # if the current widget can't accept a choices arg, fall back to using a Select widget
                field.widget = forms.Select(choices=choices)
            else:
                field.choices = choices

        # crispy forms
        self.helper = FormHelper()
        self.helper.layout = self.layout()


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
        self.time_limit_was_exceeded = kwargs.pop('time_limit_was_exceeded')

class ExperimenterModelForm(BaseModelForm):
    def process_kwargs(self, kwargs):
        self.experiment = kwargs.pop('experiment')
        self.request = kwargs.pop('request')


class StubModelForm(ModelForm):
    class Meta:
        model = ptree.session.models.StubModel
        fields = []