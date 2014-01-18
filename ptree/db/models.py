import django.db.models
from django.db.models import *
import django.forms.widgets
from django.utils.translation import ugettext_lazy
import django.forms.fields
from django.utils.text import capfirst

class NullBooleanSelect(django.forms.widgets.NullBooleanSelect):
    def __init__(self, attrs=None):
        choices = (('1', ugettext_lazy('---------')),
                   ('2', ugettext_lazy('Yes')),
                   ('3', ugettext_lazy('No')))
        super(django.forms.widgets.NullBooleanSelect, self).__init__(attrs, choices)

class _NullBooleanFormField(django.forms.fields.NullBooleanField):
    widget = NullBooleanSelect

class NullBooleanField(django.db.models.NullBooleanField):
    def formfield(self, **kwargs):
        defaults = {
            'form_class': _NullBooleanFormField,
            'required': not self.blank,
            'label': capfirst(self.verbose_name),
            'help_text': self.help_text}
        defaults.update(kwargs)
        return super(django.db.models.NullBooleanField, self).formfield(**defaults)


