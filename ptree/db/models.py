from django.db.models import *
import django.forms.widgets
from django.utils.translation import ugettext_lazy
import django.forms.fields
from django.utils.text import capfirst
import django.db.models
import easymoney
from ptree.common import expand_choice_tuples, _MoneyInput

def fix_choices_arg(kwargs):
    '''allows the programmer to define choices as a list of values rather than (value, display_value)'''
    choices = kwargs.get('choices')
    if not choices:
        return
    choices = expand_choice_tuples(choices)
    kwargs['choices'] = choices


class _PtreeModelFieldMixin(object):
    def __init__(self, *args,  **kwargs):
        self.doc = kwargs.pop('doc', None)
        fix_choices_arg(kwargs)
        kwargs.setdefault('null',True)

        # if default=None, Django will omit the blank choice from form widget
        # https://code.djangoproject.com/ticket/10792
        # that is contrary to the way pTree views blank/None values, so to correct for this,
        # we get rid of default=None args.
        # setting null=True already should make the field null
        if kwargs.has_key('default') and kwargs['default'] is None:
            kwargs.pop('default')
        super(_PtreeModelFieldMixin, self).__init__(*args, **kwargs)

class _PtreeNotNullableModelFieldMixin(object):
    def __init__(self, *args,  **kwargs):
        self.doc = kwargs.pop('doc', None)
        fix_choices_arg(kwargs)
        super(_PtreeNotNullableModelFieldMixin, self).__init__(*args, **kwargs)


class MoneyField(_PtreeModelFieldMixin, easymoney.MoneyField):
    widget = _MoneyInput



class NullBooleanField(_PtreeModelFieldMixin, NullBooleanField):
    # 2014/3/28: i just define the allowable choices on the model field, instead of customizing the widget
    # since then it works for any widget

    def __init__(self, *args,  **kwargs):
        if not kwargs.has_key('choices'):
            kwargs['choices'] = (
                (True, ugettext_lazy('Yes')),
                (False, ugettext_lazy('No'))
            )
        super(NullBooleanField, self).__init__(*args, **kwargs)

class AutoField(_PtreeModelFieldMixin, AutoField):
    pass

class BigIntegerField(_PtreeModelFieldMixin, BigIntegerField):
    pass

class BinaryField(_PtreeModelFieldMixin, BinaryField):
    pass

class BooleanField(_PtreeNotNullableModelFieldMixin, BooleanField):
    pass

class CharField(_PtreeModelFieldMixin, CharField):
    def __init__(self, *args,  **kwargs):
        kwargs.setdefault('max_length',500)
        super(CharField, self).__init__(*args, **kwargs)


class CommaSeparatedIntegerField(_PtreeModelFieldMixin, CommaSeparatedIntegerField):
    pass

class DateField(_PtreeModelFieldMixin, DateField):
    pass

class DateTimeField(_PtreeModelFieldMixin, DateTimeField):
    pass

class DecimalField(_PtreeModelFieldMixin, DecimalField):
    pass

class EmailField(_PtreeModelFieldMixin, EmailField):
    pass

class FileField(_PtreeModelFieldMixin, FileField):
    pass

class FilePathField(_PtreeModelFieldMixin, FilePathField):
    pass


class FloatField(_PtreeModelFieldMixin, FloatField):
    pass


class ImageField(_PtreeModelFieldMixin, ImageField):
    pass


class IntegerField(_PtreeModelFieldMixin, IntegerField):
    pass


class IPAddressField(_PtreeModelFieldMixin, IPAddressField):
    pass


class GenericIPAddressField(_PtreeModelFieldMixin, GenericIPAddressField):
    pass


class PositiveIntegerField(_PtreeModelFieldMixin, PositiveIntegerField):
    pass


class PositiveSmallIntegerField(_PtreeModelFieldMixin, PositiveSmallIntegerField):
    pass


class SlugField(_PtreeModelFieldMixin, SlugField):
    pass


class SmallIntegerField(_PtreeModelFieldMixin, SmallIntegerField):
    pass


class TextField(_PtreeModelFieldMixin, TextField):
    pass


class TimeField(_PtreeModelFieldMixin, TimeField):
    pass


class URLField(_PtreeModelFieldMixin, URLField):
    pass



class ManyToManyField(_PtreeModelFieldMixin, ManyToManyField):
    pass


class OneToOneField(_PtreeModelFieldMixin, OneToOneField):
    pass

