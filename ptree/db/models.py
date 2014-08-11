from django.db.models import *
import django.forms.widgets
from django.utils.translation import ugettext_lazy
import django.forms.fields
from django.utils.text import capfirst
import django.db.models
import easymoney
from otree.common import expand_choice_tuples, _MoneyInput

def fix_choices_arg(kwargs):
    '''allows the programmer to define choices as a list of values rather than (value, display_value)'''
    choices = kwargs.get('choices')
    if not choices:
        return
    choices = expand_choice_tuples(choices)
    kwargs['choices'] = choices


class _OtreeModelFieldMixin(object):
    def __init__(self, *args,  **kwargs):
        self.doc = kwargs.pop('doc', None)
        fix_choices_arg(kwargs)
        kwargs.setdefault('null',True)

        # if default=None, Django will omit the blank choice from form widget
        # https://code.djangoproject.com/ticket/10792
        # that is contrary to the way oTree views blank/None values, so to correct for this,
        # we get rid of default=None args.
        # setting null=True already should make the field null
        if kwargs.has_key('default') and kwargs['default'] is None:
            kwargs.pop('default')
        super(_OtreeModelFieldMixin, self).__init__(*args, **kwargs)

class _OtreeNotNullableModelFieldMixin(object):
    def __init__(self, *args,  **kwargs):
        self.doc = kwargs.pop('doc', None)
        fix_choices_arg(kwargs)
        super(_OtreeNotNullableModelFieldMixin, self).__init__(*args, **kwargs)


class MoneyField(_OtreeModelFieldMixin, easymoney.MoneyField):
    widget = _MoneyInput



class NullBooleanField(_OtreeModelFieldMixin, NullBooleanField):
    # 2014/3/28: i just define the allowable choices on the model field, instead of customizing the widget
    # since then it works for any widget

    def __init__(self, *args,  **kwargs):
        if not kwargs.has_key('choices'):
            kwargs['choices'] = (
                (True, ugettext_lazy('Yes')),
                (False, ugettext_lazy('No'))
            )
        super(NullBooleanField, self).__init__(*args, **kwargs)

class AutoField(_OtreeModelFieldMixin, AutoField):
    pass

class BigIntegerField(_OtreeModelFieldMixin, BigIntegerField):
    pass

class BinaryField(_OtreeModelFieldMixin, BinaryField):
    pass

class BooleanField(_OtreeNotNullableModelFieldMixin, BooleanField):
    pass

class CharField(_OtreeModelFieldMixin, CharField):
    def __init__(self, *args,  **kwargs):
        kwargs.setdefault('max_length',500)
        super(CharField, self).__init__(*args, **kwargs)


class CommaSeparatedIntegerField(_OtreeModelFieldMixin, CommaSeparatedIntegerField):
    pass

class DateField(_OtreeModelFieldMixin, DateField):
    pass

class DateTimeField(_OtreeModelFieldMixin, DateTimeField):
    pass

class DecimalField(_OtreeModelFieldMixin, DecimalField):
    pass

class EmailField(_OtreeModelFieldMixin, EmailField):
    pass

class FileField(_OtreeModelFieldMixin, FileField):
    pass

class FilePathField(_OtreeModelFieldMixin, FilePathField):
    pass


class FloatField(_OtreeModelFieldMixin, FloatField):
    pass


class ImageField(_OtreeModelFieldMixin, ImageField):
    pass


class IntegerField(_OtreeModelFieldMixin, IntegerField):
    pass


class IPAddressField(_OtreeModelFieldMixin, IPAddressField):
    pass


class GenericIPAddressField(_OtreeModelFieldMixin, GenericIPAddressField):
    pass


class PositiveIntegerField(_OtreeModelFieldMixin, PositiveIntegerField):
    pass


class PositiveSmallIntegerField(_OtreeModelFieldMixin, PositiveSmallIntegerField):
    pass


class SlugField(_OtreeModelFieldMixin, SlugField):
    pass


class SmallIntegerField(_OtreeModelFieldMixin, SmallIntegerField):
    pass


class TextField(_OtreeModelFieldMixin, TextField):
    pass


class TimeField(_OtreeModelFieldMixin, TimeField):
    pass


class URLField(_OtreeModelFieldMixin, URLField):
    pass



class ManyToManyField(_OtreeModelFieldMixin, ManyToManyField):
    pass


class OneToOneField(_OtreeModelFieldMixin, OneToOneField):
    pass

