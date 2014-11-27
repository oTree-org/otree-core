from django.db.models import *
from django.db.models.base import ModelBase
import django.forms.widgets
from django.utils.translation import ugettext_lazy
import django.forms.fields
from django.utils.text import capfirst
import django.db.models
import easymoney
from otree.common_internal import expand_choice_tuples, _CurrencyInput
import otree.common
from handy.models import PickleField
import itertools
import random
import string


class OTreeModelBase(ModelBase):
    def __new__(cls, name, bases, attrs):
        new_class = super(OTreeModelBase, cls).__new__(cls, name, bases, attrs)

        for f in new_class._meta.fields:
            if hasattr(new_class, f.name + '_choices'):
                setattr(new_class, 'get_%s_display' % f.name, make_get_display(f))

        return new_class

def make_get_display(field):
    def get_FIELD_display(self):
        choices = getattr(self, field.name + '_choices')()
        value = getattr(self, field.attname)
        return dict(expand_choice_tuples(choices))[value]
    return get_FIELD_display

class OTreeModel(Model):
    __metaclass__ = OTreeModelBase

    class Meta:
        abstract = True
Model = OTreeModel


class _OtreeModelFieldMixin(object):
    def fix_choices_arg(self, kwargs):
        '''allows the programmer to define choices as a list of values rather than (value, display_value)'''
        choices = kwargs.get('choices')
        if not choices:
            return
        choices = expand_choice_tuples(choices)
        kwargs['choices'] = choices

    def set_otree_properties(self, kwargs):
        self.doc = kwargs.pop('doc', None)


    def __init__(self, *args,  **kwargs):
        self.set_otree_properties(kwargs)
        self.fix_choices_arg(kwargs)
        super(_OtreeModelFieldMixin, self).__init__(*args, **kwargs)

    def formfield(self, *args, **kwargs):
        return super(_OtreeModelFieldMixin, self).formfield(*args, **kwargs)


class _OtreeWidgetForModelFieldMixin(object):
    """
    Give a `widget` argument to a model field in order to override the default
    widget used for this field in a model form.

    The given widget will only be used when you subclass your model form from
    otree.forms.forms.BaseModelForm.
    """

    def __init__(self, *args, **kwargs):
        self.widget = kwargs.pop('widget', None)
        super(_OtreeWidgetForModelFieldMixin, self).__init__(*args, **kwargs)


class _OtreeNullableModelFieldMixin(_OtreeModelFieldMixin, _OtreeWidgetForModelFieldMixin):
    def __init__(self, *args,  **kwargs):
        kwargs.setdefault('null',True)

        # if default=None, Django will omit the blank choice from form widget
        # https://code.djangoproject.com/ticket/10792
        # that is contrary to the way oTree views blank/None values, so to correct for this,
        # we get rid of default=None args.
        # setting null=True already should make the field null
        if kwargs.has_key('default') and kwargs['default'] is None:
            kwargs.pop('default')
        super(_OtreeNullableModelFieldMixin, self).__init__(*args, **kwargs)


class _OtreeNotNullableModelFieldMixin(_OtreeModelFieldMixin):
    pass


class MoneyField(_OtreeNullableModelFieldMixin, easymoney.MoneyField):
    widget = _CurrencyInput

    MONEY_CLASS = otree.common.Money

class CurrencyField(_OtreeNullableModelFieldMixin, easymoney.MoneyField):
    widget = _CurrencyInput

    MONEY_CLASS = otree.common.Currency

def string_generator(size=6, chars=string.ascii_uppercase + string.digits):
    return ''.join(random.choice(chars) for x in range(size))

class RandomCharField(_OtreeNotNullableModelFieldMixin, CharField):
    """
    We use this for player code, subsession code
    generates gibberish pronounceable words, like 'satonoha' or 'gimoradi'

    # See https://derrickpetzold.com/p/auto-random-character-field-django/
    """

    vowels = list('aeiou')
    consonants = list(set(string.ascii_lowercase) - set(vowels) - set('qxcyw'))

    def find_unique(self, model_instance, value, callback, *args):
        # exclude the current model instance from the queryset used in finding
        # next valid hash
        queryset = model_instance.__class__._default_manager.all()
        if model_instance.pk:
            queryset = queryset.exclude(pk=model_instance.pk)

        # form a kwarg dict used to implement any unique_together constraints
        kwargs = {}
        for params in model_instance._meta.unique_together:
            if self.attname in params:
                for param in params:
                    kwargs[param] = getattr(model_instance, param, None)
        kwargs[self.attname] = value

        while queryset.filter(**kwargs):
            value = callback()
            kwargs[self.attname] = value
        return value

    def __init__(self, *args, **kwargs):
        kwargs.setdefault('blank', True)
        self.length = kwargs.pop('length', 8)
        kwargs['max_length'] = self.length

        super(RandomCharField, self).__init__(*args, **kwargs)

    def generate_chars(self, *args, **kwargs):
        chars = []
        n = self.length
        char_sets = [self.consonants, self.vowels]
        for char_set in itertools.cycle(char_sets):
            n -= 1
            if n < 0:
                break
            chars.append(random.choice(char_set))

        return ''.join(chars)

    def pre_save(self, model_instance, add):
        if not add:
            return getattr(model_instance, self.attname)

        initial = self.generate_chars()
        value = self.find_unique(model_instance, initial, self.generate_chars)
        setattr(model_instance, self.attname, value)
        return value

    def get_internal_type(self):
        return "CharField"



class PickleField(_OtreeNullableModelFieldMixin, PickleField):
    pass

class NullBooleanField(_OtreeNullableModelFieldMixin, NullBooleanField):
    # 2014/3/28: i just define the allowable choices on the model field, instead of customizing the widget
    # since then it works for any widget

    def __init__(self, *args,  **kwargs):
        if not kwargs.has_key('choices'):
            kwargs['choices'] = (
                (True, ugettext_lazy('Yes')),
                (False, ugettext_lazy('No'))
            )
        super(NullBooleanField, self).__init__(*args, **kwargs)

class AutoField(_OtreeNullableModelFieldMixin, AutoField):
    pass

class BigIntegerField(_OtreeNullableModelFieldMixin, BigIntegerField):
    pass

class BinaryField(_OtreeNullableModelFieldMixin, BinaryField):
    pass

class BooleanField(_OtreeNotNullableModelFieldMixin, BooleanField):
    pass

class CharField(_OtreeNullableModelFieldMixin, CharField):
    def __init__(self, *args,  **kwargs):
        kwargs.setdefault('max_length',500)
        super(CharField, self).__init__(*args, **kwargs)


class CommaSeparatedIntegerField(_OtreeNullableModelFieldMixin, CommaSeparatedIntegerField):
    pass

class DateField(_OtreeNullableModelFieldMixin, DateField):
    pass

class DateTimeField(_OtreeNullableModelFieldMixin, DateTimeField):
    pass

class DecimalField(_OtreeNullableModelFieldMixin, DecimalField):
    pass

class EmailField(_OtreeNullableModelFieldMixin, EmailField):
    pass

class FileField(_OtreeNullableModelFieldMixin, FileField):
    pass

class FilePathField(_OtreeNullableModelFieldMixin, FilePathField):
    pass


class FloatField(_OtreeNullableModelFieldMixin, FloatField):
    pass


class ImageField(_OtreeNullableModelFieldMixin, ImageField):
    pass


class IntegerField(_OtreeNullableModelFieldMixin, IntegerField):
    pass


class IPAddressField(_OtreeNullableModelFieldMixin, IPAddressField):
    pass


class GenericIPAddressField(_OtreeNullableModelFieldMixin, GenericIPAddressField):
    pass


class PositiveIntegerField(_OtreeNullableModelFieldMixin, PositiveIntegerField):
    pass


class PositiveSmallIntegerField(_OtreeNullableModelFieldMixin, PositiveSmallIntegerField):
    pass


class SlugField(_OtreeNullableModelFieldMixin, SlugField):
    pass


class SmallIntegerField(_OtreeNullableModelFieldMixin, SmallIntegerField):
    pass


class TextField(_OtreeNullableModelFieldMixin, TextField):
    pass


class TimeField(_OtreeNullableModelFieldMixin, TimeField):
    pass


class URLField(_OtreeNullableModelFieldMixin, URLField):
    pass



class ManyToManyField(_OtreeNullableModelFieldMixin, ManyToManyField):
    pass


class OneToOneField(_OtreeNullableModelFieldMixin, OneToOneField):
    pass

