from django import forms
import templatetags.ptreefilters
import ayah
from django.conf import settings

import ptree.views.abstract
from ptree.models.common import Symbols

class FormMixin(object):

    # In general, pTree does not allow a user to go back and change their answer on a previous page,
    # since that often defeats the purpose of the game (e.g. eliciting an honest answer).
    # But you can put it in rewritable_fields to make it an exception.
    rewritable_fields = []

    def __init__(self, *args, **kwargs):
        self.participant = kwargs.pop('participant')
        self.match = kwargs.pop('match')
        self.treatment = kwargs.pop('treatment')
        self.request = kwargs.pop('request')
        self.experiment = kwargs.pop('experiment')

        super(FormMixin, self).__init__(*args, **kwargs)
        self.customize()
        self.fields[Symbols.current_view_index] = forms.IntegerField(widget=forms.HiddenInput())
        self.fields[Symbols.current_view_index].initial = self.request.session.get(Symbols.current_view_index, 0)



    def customize(self):
        """Customize your form fields here"""

    def make_field_currency_choices(self, field_name, amounts):
        amount_choices = [(amount, templatetags.ptreefilters.currency(amount)) for amount in amounts]
        self.fields[field_name].choices = amount_choices


class BlankModelForm(FormMixin, forms.ModelForm):
    """
    Try to inherit from this class whenever you can.
    ModelForms are ofter preferable to plain Forms,
    since they take care of saving to the database,
    and they require less code to write and validate.
    """

    def clean(self):
        """Prevent the user from going back and modifying an old value."""
        cleaned_data = super(BlankModelForm, self).clean()

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

class BlankForm(FormMixin, forms.Form):
    """
    If your form fields map to a Django Model (like a Participant or Match object),
    then use BlankModelForm instead.

    Use this otherwise.
    
    If you use this class, a user can go back and re-submit,
    unless you block against that explicitly after form validation."""
    pass


class StartForm(BlankForm):
    """Form rather than ModelForm,
    since it can be used with many different models"""
    name = forms.CharField(max_length = 50)
    
class CaptchaAreYouAHumanForm(BlankForm):
    """
    CAPTCHA from AreYouHuman.com
    """

    def clean(self):
        cleaned_data = super(CaptchaAreYouAHumanForm, self).clean()
        secret = self.data['session_secret']

        ayah.configure(settings.AYAH_PUBLISHER_KEY, settings.AYAH_SCORING_KEY)
        passed = ayah.score_result(secret)
        if passed:
            if not self.request.session.get('captchas_completed'):
                self.request.session['captchas_completed'] = 1
            else:
                self.request.session['captchas_completed'] += 1
            return cleaned_data
        else:
            raise forms.ValidationError("Please try again.")
