from django import forms
import templatetags.ptreefilters
from django.conf import settings

import ptree.views.abstract
from ptree.models.common import Symbols

class FormMixin(object):

    # In general, pTree does not allow a user to go back and change their answer on a previous page,
    # since that often defeats the purpose of the game (e.g. eliciting an honest answer).
    # But you can put it in rewritable_fields to make it an exception.
    ## UPDATE: deprecated for now
    # rewritable_fields = []

    def __init__(self, *args, **kwargs):
        self.participant = kwargs.pop('participant')
        self.match = kwargs.pop('match')
        self.treatment = kwargs.pop('treatment')
        self.experiment = kwargs.pop('experiment')
        self.request = kwargs.pop('request')

        initial = kwargs.get('initial', {})
        initial.update(self.get_field_initial_values())
        kwargs['initial'] = initial
        super(FormMixin, self).__init__(*args, **kwargs)

        for field_name, label in self.get_field_labels().items():
            self.fields[field_name].label = label

        for field_name, choices in self.get_field_choices().items():
            self.fields[field_name].widget = forms.Select(choices=choices)
            #self.fields[field_name].choices = choices


        self.customize()

    def get_field_initial_values(self):
        """Return a dict of any initial values"""
        return {}

    def get_field_choices(self):
        return {}

    def get_field_labels(self):
        return {}

    def customize(self):
        """Make any customizations to your field forms that are not covered by the other methods"""

    def make_field_currency_choices(self, amounts):
        return [(amount, templatetags.ptreefilters.currency(amount)) for amount in amounts]


class ModelForm(FormMixin, forms.ModelForm):
    """
    Try to inherit from this class whenever you can.
    ModelForms are ofter preferable to plain Forms,
    since they take care of saving to the database,
    and they require less code to write and validate.
    """

    def old_clean(self):
        """Prevent the user from going back and modifying an old value."""
        cleaned_data = super(ModelForm, self).clean()

        participant_resubmitted_this_form = False
        for field_name in cleaned_data.keys():
            if not field_name in self.rewritable_fields and field_name != Symbols.current_view_index:
                current_value = getattr(self.instance, field_name)
                # FIXME:
                # this assumes that the default value of these fields is None.
                # but this means I should set null=True on everything.
                if current_value is not None:
                    cleaned_data[field_name] = current_value
                    participant_resubmitted_this_form = True

        self.request.session[Symbols.participant_resubmitted_last_form] = participant_resubmitted_this_form
        return cleaned_data

class NonModelForm(FormMixin, forms.Form):
    """
    If your form fields map to a Django Model (like a Participant or Match object),
    then use ModelForm instead.

    Use this otherwise.
    
    If you use this class, a user can go back and re-submit,
    unless you block against that explicitly after form validation."""
    pass


class StartForm(NonModelForm):
    """Form rather than ModelForm,
    since it can be used with many different models"""
    name = forms.CharField(max_length = 50)
