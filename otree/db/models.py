#!/usr/bin/env python
# -*- coding: utf-8 -*-

import random
import string

from django.utils.translation import ugettext_lazy
from django.db import models
from django.db.models.fields import related
from django.db.models.base import ModelBase

from handy.models import PickleField
import easymoney

import otree.common
from otree.common_internal import expand_choice_tuples


class OTreeModelBase(ModelBase):
    def __new__(cls, name, bases, attrs):
        new_class = super(OTreeModelBase, cls).__new__(cls, name, bases, attrs)

        for f in new_class._meta.fields:
            if hasattr(new_class, f.name + '_choices'):
                attr_name = 'get_%s_display' % f.name
                setattr(new_class, attr_name, make_get_display(f))

        return new_class


def get_model(*args, **kwargs):
    return models.get_model(*args, **kwargs)


def make_get_display(field):
    def get_FIELD_display(self):
        choices = getattr(self, field.name + '_choices')()
        value = getattr(self, field.attname)
        return dict(expand_choice_tuples(choices))[value]
    return get_FIELD_display


class OTreeModel(models.Model):
    __metaclass__ = OTreeModelBase

    class Meta:
        abstract = True
Model = OTreeModel


class _OtreeModelFieldMixin(object):
    def fix_choices_arg(self, kwargs):
        '''allows the programmer to define choices as a list of values rather
        than (value, display_value)

        '''
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

        # "initial" is an alias for default. in the context of oTree, 'initial'
        # is a more intuitive name. (since the user never instantiates objects
        # themselves. also, "default" could be misleading -- people could think
        # it's the default choice in the form
        if 'initial' in kwargs:
            kwargs.setdefault('default', kwargs.pop('initial'))

        # if default=None, Django will omit the blank choice from form widget
        # https://code.djangoproject.com/ticket/10792
        # that is contrary to the way oTree views blank/None values, so to
        # correct for this, we get rid of default=None args.
        # setting null=True already should make the field null
        if 'default' in kwargs and kwargs['default'] is None:
            kwargs.pop('default')

        super(_OtreeModelFieldMixin, self).__init__(*args, **kwargs)

    def formfield(self, *args, **kwargs):
        return super(_OtreeModelFieldMixin, self).formfield(*args, **kwargs)


class _OtreeWidgetForModelFieldMixin(object):
    """Give a `widget` argument to a model field in order to override the
    default widget used for this field in a model form.

    The given widget will only be used when you subclass your model form from
    otree.forms.forms.BaseModelForm.
    """

    def __init__(self, *args, **kwargs):
        self.widget = kwargs.pop('widget', None)
        super(_OtreeWidgetForModelFieldMixin, self).__init__(*args, **kwargs)


class _OtreeNullableModelFieldMixin(_OtreeModelFieldMixin,
                                    _OtreeWidgetForModelFieldMixin):
    def __init__(self, *args,  **kwargs):
        kwargs.setdefault('null', True)

        super(_OtreeNullableModelFieldMixin, self).__init__(*args, **kwargs)


class _OtreeNotNullableModelFieldMixin(_OtreeModelFieldMixin):
    pass


class _OtreeNumericFieldMixin(object):
    def __init__(self, *args, **kwargs):
        self.bounds = kwargs.pop('bounds', None)
        super(_OtreeNumericFieldMixin, self).__init__(*args, **kwargs)

    auto_submit_default = 0


class MoneyField(_OtreeNullableModelFieldMixin,
                 _OtreeNumericFieldMixin, easymoney.MoneyField):

    MONEY_CLASS = otree.common.Money

    auto_submit_default = otree.common.Money(0)


class CurrencyField(_OtreeNullableModelFieldMixin,
                    _OtreeNumericFieldMixin, easymoney.MoneyField):

    MONEY_CLASS = otree.common.Currency

    auto_submit_default = otree.common.Currency(0)


def string_generator(size=6, chars=string.ascii_uppercase + string.digits):
    return ''.join(random.choice(chars) for x in range(size))


class RandomCharField(_OtreeNotNullableModelFieldMixin, models.CharField):
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
        char_sets = [self.consonants, self.vowels]
        for i in range(self.length):
            random_char = random.choice(char_sets[i % 2])
            chars.append(random_char)

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


class NullBooleanField(_OtreeNullableModelFieldMixin, models.NullBooleanField):
    # 2014/3/28: i just define the allowable choices on the model field,
    # instead of customizing the widget since then it works for any widget

    def __init__(self, *args,  **kwargs):
        # 2015-1-19: why is this here? isn't this the default behavior?
        if 'choices' not in kwargs:
            kwargs['choices'] = (
                (True, ugettext_lazy('Yes')),
                (False, ugettext_lazy('No'))
            )
        super(NullBooleanField, self).__init__(*args, **kwargs)

    auto_submit_default = False


class AutoField(_OtreeNullableModelFieldMixin, models.AutoField):
    pass


class BigIntegerField(_OtreeNullableModelFieldMixin,
                      _OtreeNumericFieldMixin, models.BigIntegerField):
    auto_submit_default = 0


class BinaryField(_OtreeNullableModelFieldMixin, models.BinaryField):
    pass


class BooleanField(_OtreeNotNullableModelFieldMixin, models.BooleanField):
    auto_submit_default = False


class CharField(_OtreeNullableModelFieldMixin, models.CharField):
    def __init__(self, *args,  **kwargs):
        kwargs.setdefault('max_length', 500)
        super(CharField, self).__init__(*args, **kwargs)

    auto_submit_default = ''


class CommaSeparatedIntegerField(_OtreeNullableModelFieldMixin,
                                 models.CommaSeparatedIntegerField):
    pass


class DateField(_OtreeNullableModelFieldMixin, models.DateField):
    pass


class DateTimeField(_OtreeNullableModelFieldMixin, models.DateTimeField):
    pass


class DecimalField(_OtreeNullableModelFieldMixin, models.DecimalField):
    pass


class EmailField(_OtreeNullableModelFieldMixin, models.EmailField):
    pass


class FileField(_OtreeNullableModelFieldMixin, models.FileField):
    pass


class FilePathField(_OtreeNullableModelFieldMixin, models.FilePathField):
    pass


class FloatField(_OtreeNullableModelFieldMixin, models.FloatField):
    pass


class IntegerField(_OtreeNullableModelFieldMixin,
                   _OtreeNumericFieldMixin, models.IntegerField):
    pass


class IPAddressField(_OtreeNullableModelFieldMixin, models.IPAddressField):
    pass


class GenericIPAddressField(_OtreeNullableModelFieldMixin,
                            models.GenericIPAddressField):
    pass


class PositiveIntegerField(_OtreeNullableModelFieldMixin,
                           _OtreeNumericFieldMixin,
                           models.PositiveIntegerField):
    pass


class PositiveSmallIntegerField(_OtreeNullableModelFieldMixin,
                                _OtreeNumericFieldMixin,
                                models.PositiveSmallIntegerField):
    pass


class SlugField(_OtreeNullableModelFieldMixin, models.SlugField):
    pass


class SmallIntegerField(_OtreeNullableModelFieldMixin,
                        _OtreeNumericFieldMixin, models.SmallIntegerField):
    pass


class TextField(_OtreeNullableModelFieldMixin, models.TextField):
    auto_submit_default = ''


class TimeField(_OtreeNullableModelFieldMixin, models.TimeField):
    pass


class URLField(_OtreeNullableModelFieldMixin, models.URLField):
    pass


class ForeignKey(models.ForeignKey):
    pass


class ManyToOneRel(related.ManyToOneRel):
    pass


class ManyToManyField(_OtreeNullableModelFieldMixin, models.ManyToManyField):
    pass


class OneToOneField(_OtreeNullableModelFieldMixin, models.OneToOneField):
    pass
