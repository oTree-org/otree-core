from django.db.models import *
import django.forms.widgets
from django.utils.translation import ugettext_lazy
import django.forms.fields
from django.utils.text import capfirst
import django.db.models
import easymoney
from otree.common import expand_choice_tuples, _MoneyInput

from handy.models import PickleField
class VarsField(PickleField):
    def __init__(self, *args, **kwargs):
        kwargs.setdefault('default', lambda: collections.defaultdict(list))
        super(VarsField, self).__init__(*args, **kwargs)


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

        # for quiz questions
        self.correct_answer = kwargs.pop('correct_answer', None)
        self.correct_answer_explanation = kwargs.pop('correct_answer_explanation', None)

    def __init__(self, *args,  **kwargs):
        self.set_otree_properties(kwargs)
        self.fix_choices_arg(kwargs)
        super(_OtreeModelFieldMixin, self).__init__(*args, **kwargs)


class _OtreeNullableModelFieldMixin(_OtreeModelFieldMixin):
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
    widget = _MoneyInput



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

