from django.db.models import *
import django.forms.widgets
from django.utils.translation import ugettext_lazy
import django.forms.fields
from django.utils.text import capfirst
import django.db.models
import easymoney
from ptree.common import expand_choice_tuples

def fix_choices_arg(kwargs):
    '''allows the programmer to define choices as a list of values rather than (value, display_value)'''
    choices = kwargs.get('choices')
    if not choices:
        return
    choices = expand_choice_tuples(choices)
    kwargs['choices'] = choices

class PtreeModelFieldMixin(object):
    def __init__(self, *args,  **kwargs):
        self.doc = kwargs.pop('doc', None)
        fix_choices_arg(kwargs)
        super(PtreeModelFieldMixin, self).__init__(*args, **kwargs)


class MoneyField(PtreeModelFieldMixin, easymoney.MoneyField):
    pass

class NullBooleanField(PtreeModelFieldMixin, NullBooleanField):
    # 2014/3/28: i just define the allowable choices on the model field, instead of customizing the widget
    # since then it works for any widget

    def __init__(self, *args,  **kwargs):
        if not kwargs.has_key('choices'):
            kwargs['choices'] = (
                (True, ugettext_lazy('Yes')),
                (False, ugettext_lazy('No'))
            )
        super(NullBooleanField, self).__init__(*args, **kwargs)

class AutoField(PtreeModelFieldMixin, AutoField):
    pass

class BigIntegerField(PtreeModelFieldMixin, BigIntegerField):
    pass

class BinaryField(PtreeModelFieldMixin, BinaryField):
    pass

class BooleanField(PtreeModelFieldMixin, BooleanField):
    pass

class CharField(PtreeModelFieldMixin, CharField):
    pass

class CommaSeparatedIntegerField(PtreeModelFieldMixin, CommaSeparatedIntegerField):
    pass

class DateField(PtreeModelFieldMixin, DateField):
    pass

class DateTimeField(PtreeModelFieldMixin, DateTimeField):
    pass

class DecimalField(PtreeModelFieldMixin, DecimalField):
    pass

class EmailField(PtreeModelFieldMixin, EmailField):
    pass

class FileField(PtreeModelFieldMixin, FileField):
    pass

class FilePathField(PtreeModelFieldMixin, FilePathField):
    pass


class FloatField(PtreeModelFieldMixin, FloatField):
    pass


class ImageField(PtreeModelFieldMixin, ImageField):
    pass


class IntegerField(PtreeModelFieldMixin, IntegerField):
    pass


class IPAddressField(PtreeModelFieldMixin, IPAddressField):
    pass


class GenericIPAddressField(PtreeModelFieldMixin, GenericIPAddressField):
    pass


class PositiveIntegerField(PtreeModelFieldMixin, PositiveIntegerField):
    pass


class PositiveSmallIntegerField(PtreeModelFieldMixin, PositiveSmallIntegerField):
    pass


class SlugField(PtreeModelFieldMixin, SlugField):
    pass


class SmallIntegerField(PtreeModelFieldMixin, SmallIntegerField):
    pass


class TextField(PtreeModelFieldMixin, TextField):
    pass


class TimeField(PtreeModelFieldMixin, TimeField):
    pass


class URLField(PtreeModelFieldMixin, URLField):
    pass



class ManyToManyField(PtreeModelFieldMixin, ManyToManyField):
    pass


class OneToOneField(PtreeModelFieldMixin, OneToOneField):
    pass

