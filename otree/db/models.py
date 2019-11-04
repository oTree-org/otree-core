import logging
from decimal import Decimal

from django.core import exceptions
from django.db import models
from django.utils.translation import ugettext_lazy
from idmap.models import IdMapModelBase

from otree.common import expand_choice_tuples, get_app_label_from_import_path
from otree.constants import field_required_msg
from otree.currency import Currency, RealWorldCurrency
from .idmap import IdMapModel
from django.forms import widgets as dj_widgets
from .serializedfields import _PickleField  # noqa

logger = logging.getLogger(__name__)


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
        if not hasattr(new_class._meta, 'use_strong_refs'):
            new_class._meta.use_strong_refs = False

        for f in new_class._meta.fields:
            if hasattr(new_class, f.name + '_choices'):
                attr_name = 'get_%s_display' % f.name
                setattr(new_class, attr_name, make_get_display(f))

        new_class._setattr_fields = frozenset(f.name for f in new_class._meta.fields)
        new_class._setattr_attributes = frozenset(dir(new_class))

        return new_class


def make_get_display(field):
    def get_FIELD_display(self):
        choices = getattr(self, field.name + '_choices')()
        value = getattr(self, field.attname)
        return dict(expand_choice_tuples(choices))[value]

    return get_FIELD_display


class OTreeModel(IdMapModel, metaclass=OTreeModelBase):
    class Meta:
        abstract = True

    def __repr__(self):
        return '<{} pk={}>'.format(self.__class__.__name__, self.pk)

    _is_frozen = False
    NoneType = type(None)

    _setattr_datatypes = {
        # first value should be the "recommmended" datatype,
        # because that's what we recommend in the error message.
        # it seems the habit of setting boolean values to 0 or 1
        # is very common. that's even what oTree shows in the "live update"
        # view, and the data export.
        'BooleanField': (bool, int, NoneType),
        # forms seem to save Decimal to CurrencyField
        'CurrencyField': (Currency, NoneType, int, float, Decimal),
        'FloatField': (float, NoneType, int),
        'IntegerField': (int, NoneType),
        'StringField': (str, NoneType),
        'LongStringField': (str, NoneType),
    }
    _setattr_whitelist = {
        '_initial_prep_values',
        # used by Prefetch.
        '_ordered_players',
        '_is_frozen',
        # extras on 2018-11-24
        'id',
        '_changed_fields',
        'pk',
    }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # cache it for performance
        self._super_setattr = super().__setattr__
        # originally I had:
        # self._dir_attributes = set(dir(self))
        # but this tripled memory usage when creating a session
        self._is_frozen = True

    def __setattr__(self, field_name: str, value):
        if self._is_frozen:

            if field_name in self._setattr_fields:
                # hasattr() cannot be used inside
                # a Django model's setattr, as I discovered.
                field = self._meta.get_field(field_name)

                field_type_name = type(field).__name__
                if field_type_name in self._setattr_datatypes:
                    allowed_types = self._setattr_datatypes[field_type_name]
                    if (
                        isinstance(value, allowed_types)
                        # numpy uses its own datatypes, e.g. numpy._bool,
                        # which doesn't inherit from python bool.
                        or 'numpy' in str(type(value))
                        # 2018-07-18:
                        # have an exception for the bug in the 'quiz' sample game
                        # after a while, we can remove this
                        or field_name == 'question_id'
                    ):
                        pass
                    else:
                        msg = ('{} should be set to {}, not {}.').format(
                            field_type_name,
                            allowed_types[0].__name__,
                            type(value).__name__,
                        )
                        raise TypeError(msg)
            elif (
                field_name in self._setattr_attributes
                or field_name in self._setattr_whitelist
                or
                # idmap uses _group_cache, _subsession_cache,
                # _prefetched_objects_cache, etc
                field_name.endswith('_cache')
            ):
                # django sometimes reassigns to non-field attributes that
                # were set before the class was frozen, such as
                # .pk and ._changed_fields (from SaveTheChange)
                # or assigning to a property like Player.payoff
                pass
            else:
                msg = ('{} has no field "{}".').format(
                    self.__class__.__name__, field_name
                )
                raise AttributeError(msg)

            self._super_setattr(field_name, value)
        else:
            # super() is a bit slower but only gets run during __init__
            super().__setattr__(field_name, value)

    def save(self, *args, **kwargs):
        # Use with FieldTracker
        if self.pk and hasattr(self, '_ft') and 'update_fields' not in kwargs:
            kwargs['update_fields'] = [k for k in self._ft.changed()]
        super().save(*args, **kwargs)


Model = OTreeModel


def fix_choices_arg(kwargs):
    '''allows the programmer to define choices as a list of values rather
    than (value, display_value)

    '''
    choices = kwargs.get('choices')
    if not choices:
        return
    choices = expand_choice_tuples(choices)
    kwargs['choices'] = choices


class _OtreeModelFieldMixin:
    def __init__(
        self,
        *,
        initial=None,
        label=None,
        min=None,
        max=None,
        doc='',
        widget=None,
        **kwargs,
    ):

        self.widget = widget
        self.doc = doc
        self.min = min
        self.max = max

        fix_choices_arg(kwargs)

        kwargs.setdefault('help_text', '')
        kwargs.setdefault('null', True)

        # to be more consistent with {% formfield %}
        # this is more intuitive for newbies
        kwargs.setdefault('verbose_name', label)

        # "initial" is an alias for default. in the context of oTree, 'initial'
        # is a more intuitive name. (since the user never instantiates objects
        # themselves. also, "default" could be misleading -- people could think
        # it's the default choice in the form
        kwargs.setdefault('default', initial)

        # if default=None, Django will omit the blank choice from form widget
        # https://code.djangoproject.com/ticket/10792
        # that is contrary to the way oTree views blank/None values, so to
        # correct for this, we get rid of default=None args.
        # setting null=True already should make the field null
        if 'default' in kwargs and kwargs['default'] is None:
            kwargs.pop('default')

        super().__init__(**kwargs)

    def formfield(self, **kwargs):
        if self.widget:
            kwargs['widget'] = self.widget
        return super().formfield(**kwargs)


class _OtreeNumericFieldMixin(_OtreeModelFieldMixin):
    auto_submit_default = 0


class BaseCurrencyField(_OtreeNumericFieldMixin, models.DecimalField):

    MONEY_CLASS = None  # need to set in subclasses

    def __init__(self, **kwargs):
        # i think it's sufficient just to store a high number;
        # this needs to be higher than decimal_places
        decimal_places = self.MONEY_CLASS.get_num_decimal_places()
        # where does this come from?
        max_digits = 12
        super().__init__(max_digits=max_digits, decimal_places=decimal_places, **kwargs)

    def deconstruct(self):
        name, path, args, kwargs = super().deconstruct()
        # 2017-09-24: why do we need to do this?
        del kwargs["decimal_places"]
        del kwargs["max_digits"]
        return name, path, args, kwargs

    def to_python(self, value):
        value = models.DecimalField.to_python(self, value)
        if value is None:
            return value

        return self.MONEY_CLASS(value)

    def get_prep_value(self, value):
        if value is None:
            return None
        return Decimal(self.to_python(value))

    def from_db_value(self, value, expression, connection):
        return self.to_python(value)


class CurrencyField(BaseCurrencyField):
    MONEY_CLASS = Currency
    auto_submit_default = Currency(0)

    def formfield(self, **kwargs):
        import otree.forms

        defaults = {
            'form_class': otree.forms.CurrencyField,
            'choices_form_class': otree.forms.CurrencyChoiceField,
        }
        defaults.update(kwargs)
        return super().formfield(**defaults)


class RealWorldCurrencyField(BaseCurrencyField):
    MONEY_CLASS = RealWorldCurrency
    auto_submit_default = RealWorldCurrency(0)

    def formfield(self, **kwargs):
        import otree.forms

        defaults = {
            'form_class': otree.forms.RealWorldCurrencyField,
            'choices_form_class': otree.forms.CurrencyChoiceField,
        }
        defaults.update(kwargs)
        return super().formfield(**defaults)


class BooleanField(_OtreeModelFieldMixin, models.BooleanField):
    def __init__(self, **kwargs):
        # usually checkbox is not required, except for consent forms.
        widget = kwargs.get('widget')
        if isinstance(widget, dj_widgets.CheckboxInput):
            kwargs.setdefault('blank', True)

        # we need to set explicitly because otherwise the empty choice will show up as
        # "Unknown" in a select widget. This makes it set to '-----------'.
        kwargs.setdefault(
            'choices', [(True, ugettext_lazy('Yes')), (False, ugettext_lazy('No'))]
        )
        super().__init__(**kwargs)

    auto_submit_default = False


class StringField(_OtreeModelFieldMixin, models.CharField):
    '''
    Many people are already using initial=None, and i don't think it's
    causing any problems, even though Django recommends against that, but
    that's for forms on pages that get viewed multiple times
    '''

    def __init__(
        self,
        *,
        # varchar max length doesn't affect performance or even storage
        # size; it's just for validation. so, to be easy to use,
        # there is no reason for oTree to set a short default length
        # for CharFields. The main consideration is that MySQL cannot index
        # varchar longer than 255 chars, but that is not relevant here
        # because oTree only uses indexes for fields defined in otree-core,
        # which have explicit max_lengths anyway.
        max_length=10000,
        **kwargs,
    ):

        super().__init__(max_length=max_length, **kwargs)

    auto_submit_default = ''


class DecimalField(_OtreeNumericFieldMixin, models.DecimalField):
    pass


class FloatField(_OtreeNumericFieldMixin, models.FloatField):
    pass


class IntegerField(_OtreeNumericFieldMixin, models.IntegerField):
    pass


class PositiveIntegerField(_OtreeNumericFieldMixin, models.PositiveIntegerField):
    pass


class LongStringField(_OtreeModelFieldMixin, models.TextField):
    auto_submit_default = ''


MSG_DEPRECATED_FIELD = """
{FieldName} does not exist in oTree. 
You should either replace it with one of oTree's field types, or import it from Django directly.
Note that Django model fields do not accept oTree-specific arguments like label= and widget=.
""".replace(
    '\n', ' '
)


def make_deprecated_field(FieldName):
    def DeprecatedField(*args, **kwargs):
        # putting the msg on a separate line gives better tracebacks
        raise Exception(MSG_DEPRECATED_FIELD.format(FieldName))

    return DeprecatedField


ManyToOneRel = make_deprecated_field("ManyToOneRel")
ManyToManyField = make_deprecated_field("ManyToManyField")
OneToOneField = make_deprecated_field("OneToOneField")
AutoField = make_deprecated_field("AutoField")
BigIntegerField = make_deprecated_field("BigIntegerField")
BinaryField = make_deprecated_field("BinaryField")
EmailField = make_deprecated_field("EmailField")
FileField = make_deprecated_field("FileField")
GenericIPAddressField = make_deprecated_field("GenericIPAddressField")
PositiveSmallIntegerField = make_deprecated_field("PositiveSmallIntegerField")
SlugField = make_deprecated_field("SlugField")
SmallIntegerField = make_deprecated_field("SmallIntegerField")
TimeField = make_deprecated_field("TimeField")
URLField = make_deprecated_field("URLField")
DateField = make_deprecated_field("DateField")
DateTimeField = make_deprecated_field("DateTimeField")


CharField = StringField
TextField = LongStringField
# keep ForeignKey around
ForeignKey = models.ForeignKey


CASCADE = models.CASCADE
