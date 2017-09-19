#!/usr/bin/env python
# -*- coding: utf-8 -*-
from __future__ import absolute_import

import six

from django.db import models
from django.db.models.fields import related
from django.core import exceptions
from django.utils.translation import ugettext_lazy
from django.apps import apps


import easymoney

from idmap.models import IdMapModelBase
from .idmap import IdMapModel

import otree.common
from otree.common_internal import (
    expand_choice_tuples, get_app_label_from_import_path)
from otree.constants_internal import field_required_msg
from otree_save_the_change.mixins import SaveTheChange

# this is imported from other modules
from .serializedfields import _PickleField

class _JSONField(models.TextField):
    '''just keeping around so that Migrations don't crash'''
    pass


class OTreeModelBase(IdMapModelBase):
    def __new__(mcs, name, bases, attrs):
        meta = attrs.get("Meta")
        module = attrs.get("__module__")
        is_concrete = not getattr(meta, "abstract", False)
        app_label = getattr(meta, "app_label", "")

        if is_concrete and module and not app_label:
            if meta is None:
                meta = type("Meta", (), {})
            app_label = get_app_label_from_import_path(module)
            meta.app_label = app_label
            meta.db_table = "{}_{}".format(app_label, name.lower())
            # i think needs to be here even though it's set on base model,
            # because meta is not inherited (but not tested this)
            meta.use_strong_refs = True
            attrs["Meta"] = meta

        new_class = super().__new__(mcs, name, bases, attrs)

        # 2015-12-22: this probably doesn't work anymore,
        # since we moved _choices to views.py
        # but we can tell users they can define FOO_choices in models.py,
        # and then call it in the equivalent method in views.py
        for f in new_class._meta.fields:
            if hasattr(new_class, f.name + '_choices'):
                attr_name = 'get_%s_display' % f.name
                setattr(new_class, attr_name, make_get_display(f))

        return new_class


def get_model(*args, **kwargs):
    return apps.get_model(*args, **kwargs)


def make_get_display(field):
    def get_FIELD_display(self):
        choices = getattr(self, field.name + '_choices')()
        value = getattr(self, field.attname)
        return dict(expand_choice_tuples(choices))[value]

    return get_FIELD_display


class OTreeModel(SaveTheChange, IdMapModel, metaclass=OTreeModelBase):

    class Meta:
        abstract = True

    def __repr__(self):
        return '<{} pk={}>'.format(self.__class__.__name__, self.pk)


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

        # Give a `widget` argument to a model field in order to override the
        # default widget used for this field in a model form.

        # The given widget will only be used when you subclass your model form from
        # otree.forms.forms.BaseModelForm.

        self.widget = kwargs.pop('widget', None)
        self.doc = kwargs.pop('doc', None)
        self.min = kwargs.pop('min', None)
        self.max = kwargs.pop('max', None)

    def __init__(
            # list args explicitly so they show up in IDE autocomplete.
            # Hide the ones that oTree users will rarely need, like
            # db_index, primary_key, etc...
            self,
            *,
            choices=None,
            widget=None,
            initial=None,
            verbose_name=None,
            doc='',
            min=None,
            max=None,
            blank=False,
            null=True,
            help_text='',
            **kwargs):

        # ...but put them all back into kwargs so that there is a consistent
        # interface to work with them
        kwargs.update(dict(
            choices=choices,
            widget=widget,
            initial=initial,
            verbose_name=verbose_name,
            doc=doc,
            min=min,
            max=max,
            blank=blank,
            null=null,
            help_text=help_text,
        ))

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

        super(_OtreeModelFieldMixin, self).__init__(**kwargs)


class _OtreeNumericFieldMixin(_OtreeModelFieldMixin):
    auto_submit_default = 0


class RealWorldCurrencyField(_OtreeNumericFieldMixin, easymoney.MoneyField):
    MONEY_CLASS = otree.common.RealWorldCurrency

    auto_submit_default = otree.common.RealWorldCurrency(0)


class CurrencyField(_OtreeNumericFieldMixin, easymoney.MoneyField):
    MONEY_CLASS = otree.common.Currency

    auto_submit_default = otree.common.Currency(0)



class BooleanField(_OtreeModelFieldMixin, models.NullBooleanField):
    # 2014/3/28: i just define the allowable choices on the model field,
    # instead of customizing the widget since then it works for any widget

    def __init__(self,
                 *,
                 choices=None,
                 widget=None,
                 initial=None,
                 verbose_name=None,
                 doc='',
                 null=True,
                 help_text='',
                 **kwargs):
        # 2015-1-19: why is this here? isn't this the default behavior?
        # 2013-1-26: ah, because we don't want the "----" (None) choice
        if choices is None:
            choices = (
                (True, ugettext_lazy('Yes')),
                (False, ugettext_lazy('No'))
            )

        # We need to store whether blank is explicitly specified or not. If
        # it's not specified explicitly (which will make it default to False)
        # we need to special case validation logic in the form field if a
        # checkbox input is used.
        self._blank_is_explicit = 'blank' in kwargs

        super(BooleanField, self).__init__(
            choices=choices,
            widget=widget,
            initial=initial,
            verbose_name=verbose_name,
            doc=doc,
            null=null,
            help_text=help_text,
            **kwargs)

        # you cant override "blank" or you will destroy the migration system
        self.allow_blank = bool(kwargs.get("blank"))

    auto_submit_default = False

    def clean(self, value, model_instance):
        if value is None and not self.allow_blank:
            raise exceptions.ValidationError(field_required_msg)
        return super(BooleanField, self).clean(value, model_instance)

    def formfield(self, *args, **kwargs):
        from otree import widgets

        is_checkbox_widget = isinstance(self.widget, widgets.CheckboxInput)
        if not self._blank_is_explicit and is_checkbox_widget:
            kwargs.setdefault('required', False)
        else:
            # this use the allow_blank for the form fields
            kwargs.setdefault('required', not self.allow_blank)

        return super(BooleanField, self).formfield(*args, **kwargs)


class AutoField(_OtreeModelFieldMixin, models.AutoField):
    pass


class BigIntegerField(
        _OtreeNumericFieldMixin, models.BigIntegerField):
    auto_submit_default = 0


class BinaryField(_OtreeModelFieldMixin, models.BinaryField):
    pass


# FIXME: CharField should never be nullable, otherwise we have to check for two
#        empty values: None and the empty string.
class CharField(_OtreeModelFieldMixin, models.CharField):
    def __init__(
            self,
            *,
            choices=None,
            widget=None,
            initial=None,
            verbose_name=None,
            doc='',
            # varchar max length doesn't affect performance or even storage
            # size; it's just for validation. so, to be easy to use,
            # there is no reason for oTree to set a short default length
            # for CharFields. The main consideration is that MySQL cannot index
            # varchar longer than 255 chars, but that is not relevant here
            # because oTree only uses indexes for fields defined in otree-core,
            # which have explicit max_lengths anyway.
            max_length=10000,
            blank=False,
            null=True,
            help_text='',
            **kwargs):
        super(CharField, self).__init__(
            choices=choices,
            widget=widget,
            initial=initial,
            verbose_name=verbose_name,
            doc=doc,
            max_length=max_length,
            blank=blank,
            null=null,
            help_text=help_text,
            **kwargs)

    auto_submit_default = ''


class CommaSeparatedIntegerField(_OtreeModelFieldMixin,
                                 models.CommaSeparatedIntegerField):
    pass


class DateField(_OtreeModelFieldMixin, models.DateField):
    pass


class DateTimeField(_OtreeModelFieldMixin, models.DateTimeField):
    pass


class DecimalField(
        _OtreeNumericFieldMixin,
        models.DecimalField):
    pass


class EmailField(_OtreeModelFieldMixin, models.EmailField):
    pass


class FileField(_OtreeModelFieldMixin, models.FileField):
    pass


class FilePathField(_OtreeModelFieldMixin, models.FilePathField):
    pass


class FloatField(
        _OtreeNumericFieldMixin,
        models.FloatField):
    pass


class IntegerField(
        _OtreeNumericFieldMixin, models.IntegerField):
    pass


class GenericIPAddressField(_OtreeModelFieldMixin,
                            models.GenericIPAddressField):
    pass


class PositiveIntegerField(
        _OtreeNumericFieldMixin,
        models.PositiveIntegerField):
    pass


class PositiveSmallIntegerField(
        _OtreeNumericFieldMixin,
        models.PositiveSmallIntegerField):
    pass


class SlugField(_OtreeModelFieldMixin, models.SlugField):
    pass


class SmallIntegerField(
        _OtreeNumericFieldMixin, models.SmallIntegerField):
    pass


class TextField(_OtreeModelFieldMixin, models.TextField):
    auto_submit_default = ''


class TimeField(_OtreeModelFieldMixin, models.TimeField):
    pass


class URLField(_OtreeModelFieldMixin, models.URLField):
    pass


ForeignKey = models.ForeignKey
ManyToOneRel = related.ManyToOneRel
ManyToManyField = models.ManyToManyField
OneToOneField = models.OneToOneField
