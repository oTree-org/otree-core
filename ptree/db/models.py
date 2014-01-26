from django.db.models import *
import django.forms.widgets
from django.utils.translation import ugettext_lazy
import django.forms.fields
from django.utils.text import capfirst
import django.db.models

# leading underscore so it doesn't show up in autocomplete
class _NullBooleanSelect(django.forms.widgets.NullBooleanSelect):
    def __init__(self, attrs=None):
        choices = (('1', ugettext_lazy('---------')),
                   ('2', ugettext_lazy('Yes')),
                   ('3', ugettext_lazy('No')))
        super(django.forms.widgets.NullBooleanSelect, self).__init__(attrs, choices)

class _NullBooleanFormField(django.forms.fields.NullBooleanField):
    widget = _NullBooleanSelect

class NullBooleanField(NullBooleanField):
    def formfield(self, **kwargs):
        defaults = {
            'form_class': _NullBooleanFormField,
            'required': not self.blank,
            'label': capfirst(self.verbose_name),
            'help_text': self.help_text}
        defaults.update(kwargs)
        return super(django.db.models.NullBooleanField, self).formfield(**defaults)

    def __init__(self, *args,  **kwargs):
        self.doc = kwargs.pop('doc', None)
        super(NullBooleanField, self).__init__(*args, **kwargs)

class AutoField(AutoField):
    def __init__(self, *args,  **kwargs):
        self.doc = kwargs.pop('doc', None)
        super(AutoField, self).__init__(*args, **kwargs)

class BigIntegerField(BigIntegerField):
    def __init__(self, *args,  **kwargs):
        self.doc = kwargs.pop('doc', None)
        super(BigIntegerField, self).__init__(*args, **kwargs)

class BinaryField(BinaryField):
    def __init__(self, *args,  **kwargs):
        self.doc = kwargs.pop('doc', None)
        super(BinaryField, self).__init__(*args, **kwargs)

class BooleanField(BooleanField):
    def __init__(self, *args,  **kwargs):
        self.doc = kwargs.pop('doc', None)
        super(BooleanField, self).__init__(*args, **kwargs)

class CharField(CharField):
    def __init__(self, *args,  **kwargs):
        self.doc = kwargs.pop('doc', None)
        super(CharField, self).__init__(*args, **kwargs)

class CommaSeparatedIntegerField(CommaSeparatedIntegerField):
    def __init__(self, *args,  **kwargs):
        self.doc = kwargs.pop('doc', None)
        super(CommaSeparatedIntegerField, self).__init__(*args, **kwargs)

class DateField(DateField):
    def __init__(self, *args,  **kwargs):
        self.doc = kwargs.pop('doc', None)
        super(DateField, self).__init__(*args, **kwargs)

class DateTimeField(DateTimeField):
    def __init__(self, *args,  **kwargs):
        self.doc = kwargs.pop('doc', None)
        super(DateTimeField, self).__init__(*args, **kwargs)

class DecimalField(DecimalField):
    def __init__(self, *args,  **kwargs):
        self.doc = kwargs.pop('doc', None)
        super(DecimalField, self).__init__(*args, **kwargs)

class EmailField(EmailField):
    def __init__(self, *args,  **kwargs):
        self.doc = kwargs.pop('doc', None)
        super(EmailField, self).__init__(*args, **kwargs)

class FileField(FileField):
    def __init__(self, *args,  **kwargs):
        self.doc = kwargs.pop('doc', None)
        super(FileField, self).__init__(*args, **kwargs)

class FilePathField(FilePathField):
    def __init__(self, *args,  **kwargs):
        self.doc = kwargs.pop('doc', None)
        super(FilePathField, self).__init__(*args, **kwargs)

class FloatField(FloatField):
    def __init__(self, *args,  **kwargs):
        self.doc = kwargs.pop('doc', None)
        super(FloatField, self).__init__(*args, **kwargs)

class ImageField(ImageField):
    def __init__(self, *args,  **kwargs):
        self.doc = kwargs.pop('doc', None)
        super(ImageField, self).__init__(*args, **kwargs)

class IntegerField(IntegerField):
    def __init__(self, *args,  **kwargs):
        self.doc = kwargs.pop('doc', None)
        super(IntegerField, self).__init__(*args, **kwargs)

class IPAddressField(IPAddressField):
    def __init__(self, *args,  **kwargs):
        self.doc = kwargs.pop('doc', None)
        super(IPAddressField, self).__init__(*args, **kwargs)

class GenericIPAddressField(GenericIPAddressField):
    def __init__(self, *args,  **kwargs):
        self.doc = kwargs.pop('doc', None)
        super(GenericIPAddressField, self).__init__(*args, **kwargs)

class PositiveIntegerField(PositiveIntegerField):
    def __init__(self, *args,  **kwargs):
        self.doc = kwargs.pop('doc', None)
        super(PositiveIntegerField, self).__init__(*args, **kwargs)

class PositiveSmallIntegerField(PositiveSmallIntegerField):
    def __init__(self, *args,  **kwargs):
        self.doc = kwargs.pop('doc', None)
        super(PositiveSmallIntegerField, self).__init__(*args, **kwargs)

class SlugField(SlugField):
    def __init__(self, *args,  **kwargs):
        self.doc = kwargs.pop('doc', None)
        super(SlugField, self).__init__(*args, **kwargs)

class SmallIntegerField(SmallIntegerField):
    def __init__(self, *args,  **kwargs):
        self.doc = kwargs.pop('doc', None)
        super(SmallIntegerField, self).__init__(*args, **kwargs)

class TextField(TextField):
    def __init__(self, *args,  **kwargs):
        self.doc = kwargs.pop('doc', None)
        super(TextField, self).__init__(*args, **kwargs)

class TimeField(TimeField):
    def __init__(self, *args,  **kwargs):
        self.doc = kwargs.pop('doc', None)
        super(TimeField, self).__init__(*args, **kwargs)

class URLField(URLField):
    def __init__(self, *args,  **kwargs):
        self.doc = kwargs.pop('doc', None)
        super(URLField, self).__init__(*args, **kwargs)

class ForeignKey(ForeignKey):
    def __init__(self, *args,  **kwargs):
        self.doc = kwargs.pop('doc', None)
        super(ForeignKey, self).__init__(*args, **kwargs)

class ManyToManyField(ManyToManyField):
    def __init__(self, *args,  **kwargs):
        self.doc = kwargs.pop('doc', None)
        super(ManyToManyField, self).__init__(*args, **kwargs)

class OneToOneField(OneToOneField):
    def __init__(self, *args,  **kwargs):
        self.doc = kwargs.pop('doc', None)
        super(OneToOneField, self).__init__(*args, **kwargs)