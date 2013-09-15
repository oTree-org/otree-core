import {{ app_name }}.models
from django import forms
import ptree.forms

class MyForm(ptree.forms.BlankModelForm):
    # ptree.forms.BlankModelForm is based on a Django ModelForm.
    # for documentation on ModelForms (which explains the code you have to write below), see here:
    # https://docs.djangoproject.com/en/dev/topics/forms/modelforms/#modelform
    
    class Meta:
        # What model does this Form modify? It's usually either Match or Player.
        model = {{ app_name }}.models.Match 
         
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

        # you can raise a validation error like this:
        if not self.treatment.some_random_method(my_field):
            raise ValidationError
        
        return my_field

# add more forms as you wish...        