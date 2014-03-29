# -*- coding: utf-8 -*-
import {{ app_name }}.models as models
from django import forms
from django.forms import ValidationError
from {{ app_name }}.utilities import ParticipantMixin, ExperimenterMixin
from django.utils.translation import ugettext_lazy as _
import ptree.forms

class MyForm(ParticipantMixin, ptree.forms.Form):

    class Meta:
        model = models.Participant
        fields = ['my_field']

    def validate_my_field(self, value):
        if not self.treatment.your_method_here(value):
            raise ValidationError('Invalid input')

    def labels(self):
        return {}

    def initial_values(self):
        return {}
