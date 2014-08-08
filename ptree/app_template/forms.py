# -*- coding: utf-8 -*-
import {{ app_name }}.models as models
from django import forms
from {{ app_name }}.utilities import Form
from crispy_forms.layout import HTML

class MyForm(Form):

    class Meta:
        model = models.Participant
        fields = ['my_field']

    def my_field_error_message(self, value):
        if not self.treatment.your_method_here(value):
            return 'Error message goes here'

    def labels(self):
        return {}

    def defaults(self):
        return {}

    def order(self):
        pass
