import {{ app_name }}.models as models
from django import forms
from {{ app_name }}.utilities import ModelForm
from django.utils.translation import ugettext_lazy as _

class StartForm(ModelForm):
    class Meta:
        model = models.Participant
        fields = []

class MyForm(ModelForm):

    class Meta:
        # What model does this Form modify? It's usually either Match or Participant.
        model = models.Participant
         
         # the fields on the above model that this form includes
        fields = ['my_field']

    # clean a field during validation.
    # you can have as many of these as you want for as many fields as you want to make custom validation for.
    # writing these methods is described here:
    # https://docs.djangoproject.com/en/dev/ref/forms/validation/#cleaning-a-specific-field-attribute
    # replace my_field with your field name.
    # this includes change the method name from clean_my_field to clean_[you field's name]
    def clean_my_field(self):
        my_field = self.cleaned_data['my_field']

        if self.time_limit_was_exceeded:
            """You can reject the user's input in favor of a default"""

        # you can raise a validation error like this:
        if not self.treatment.your_method_here(my_field):
            raise forms.ValidationError('Invalid input')
        
        return my_field

    def field_choices(self):
        return {}

    def field_labels(self):
        return {}

    def field_initial_values(self):
        return {}

# add more forms as you wish...