import {{ app_name }}.models as models
from django import forms
from {{ app_name }}.utilities import InThisApp
from django.utils.translation import ugettext_lazy as _
import ptree.forms

class StartForm(InThisApp, ptree.forms.ModelForm):
    class Meta:
        model = models.Participant
        fields = []

class MyForm(InThisApp, ptree.forms.ModelForm):

    class Meta:
        model = models.Participant
        fields = ['my_field']

    def clean_my_field(self):
        my_field = self.cleaned_data['my_field']

        if not self.treatment.your_method_here(my_field):
            raise forms.ValidationError('Invalid input')
        
        return my_field

    def field_choices(self):
        return {}

    def field_labels(self):
        return {}

    def field_initial_values(self):
        return {}