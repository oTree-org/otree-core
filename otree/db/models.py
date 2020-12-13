import logging
from decimal import Decimal

from django.db import models
from django.db.models import QuerySet, Manager
from django.db.models.base import ModelBase
from django.db.models.manager import BaseManager
from django.db.models.query import ModelIterable
from django.forms import widgets as dj_widgets
from django.utils.translation import ugettext_lazy

from otree.common import expand_choice_tuples, get_app_label_from_import_path
from otree.currency import Currency, RealWorldCurrency
from . import idmap
from .vars import _PickleField, VarsMixin  # noqa

logger = logging.getLogger(__name__)


class OTreeModelBase(ModelBase):
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
            attrs["Meta"] = meta

        new_class = super().__new__(mcs, name, bases, attrs)

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


class IdMapQuerySet(QuerySet):
    model = None  # type: OTreeModel

    def _idmap_clone(self):
        '''TODO: what is the purpose of this?'''
        clone = self._clone()
        clone.__dict__.update({'_fields': None, '_iterable_class': ModelIterable})
        return clone

    def get(self, *args, **kwargs):
        if not (idmap.is_active and self._iterable_class is ModelIterable):
            return super().get(*args, **kwargs)
        cache_kwargs = kwargs
        if len(args) == 1:
            # from django.db.models.query_utils import Q
            [q] = args
            cache_kwargs = dict(q.children)
        is_unsupported_lookup = bool(
            set(cache_kwargs.keys())
            - idmap.SUPPORTED_CACHE_LOOKUP_FIELDS[self.model.__name__]
        )

        instance = None
        if not is_unsupported_lookup:
            instance = self.model.get_cached_instance(**cache_kwargs)

        if instance is None:
            clone = self._idmap_clone()
            clone.query.clear_select_fields()
            clone.query.default_cols = True
            instance = super(IdMapQuerySet, clone).get(*args, **kwargs)
            if is_unsupported_lookup:
                # check if it already exists in cache
                cached_instance = self.model.get_cached_instance(id=instance.id)
                if cached_instance:
                    instance = cached_instance
            self.model.cache_if_necessary(instance)
        return instance


class IdMapManager(BaseManager.from_queryset(IdMapQuerySet), Manager):
    pass


class OTreeModel(models.Model, metaclass=OTreeModelBase):
    ####### IDMAP STUFF #######
    objects = IdMapManager()

    class Meta:
        abstract = True
        base_manager_name = 'objects'
        default_manager_name = 'objects'

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
        # we still need some kind of 'save the change' logic because we don't want .update() queries
        # to be overwritten when the player model is saved.
        self._update_fields = set()
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
            if field_name in self._setattr_fields and field_name not in ['id']:
                self._update_fields.add(field_name)
            self._super_setattr(field_name, value)
        else:
            # super() is a bit slower but only gets run during __init__
            super().__setattr__(field_name, value)

    def save(self, *args, **kwargs):
        if not self._state.adding:
            update_fields = self._update_fields
            if hasattr(self, '_vars_changed') and self._vars_changed():
                update_fields.add('vars')
            kwargs.setdefault('update_fields', list(self._update_fields))
        super().save(*args, **kwargs)
        # needed when we create a new group
        self.cache_if_necessary()

    def cache_if_necessary(self):
        if idmap.is_active:
            self.cache_instance(self)

    @classmethod
    def from_db(cls, db, field_names, values):
        '''i should figure out exactly when this is used. it apparently is required. maybe for FKs'''
        instance_id = dict(zip(field_names, values))['id']
        instance = cls.get_cached_instance(id=instance_id)
        if not instance:
            instance = super().from_db(db, field_names, values)
            cls.cache_if_necessary(instance)
        return instance

    def refresh_from_db(self, using=None, fields=None):
        self.flush_cached_instance(self)
        super().refresh_from_db(using, fields)
        self.cache_if_necessary()

    @classmethod
    def _get_cache_key(cls, id, **kwargs):
        return id

    @classmethod
    def get_cached_instance(cls, **kwargs):
        if 'pk' in kwargs:
            kwargs['id'] = kwargs.pop('pk')
        return cls._get_cached_instance(**kwargs)


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
        kwargs.setdefault('widget', dj_widgets.RadioSelect)
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


# currently it's just a regular model, but we might customize it in the future
# (e.g. custom model manager)
ExtraModel = models.Model


class Link(models.ForeignKey):
    def __init__(self, to):
        # should we allow it to be null? That could be useful for network games.
        # or for games where we create resources that are initially unclaimed by users.
        # it's necessary for devserver auto migrations. if you add or rename a Link field,
        # the existing records must have null.
        # the biggest concern is that
        # people will forget to pass player or group.
        # but i guess i have no choice. anyway this is more advanced functionality.
        kwargs = dict(to=to, on_delete=models.CASCADE, null=True)
        # don't make reverse relation, then we don't have to worry about conflicting
        # related_name error.
        super().__init__(related_name="+", **kwargs)

    def deconstruct(self):
        name, path, args, kwargs = super().deconstruct()
        new_kwargs = dict(to=kwargs['to'])
        return name, path, (), new_kwargs

    def formfield(self, *args, **kwargs):
        raise Exception('oTree Link cannot be used as formfield')


class DecimalField(_OtreeNumericFieldMixin, models.DecimalField):
    pass


Model = models.Model
ForeignKey = models.ForeignKey


class FloatField(_OtreeNumericFieldMixin, models.FloatField):
    pass


class IntegerField(_OtreeNumericFieldMixin, models.IntegerField):
    pass


class PositiveIntegerField(_OtreeNumericFieldMixin, models.PositiveIntegerField):
    pass


class LongStringField(_OtreeModelFieldMixin, models.TextField):
    auto_submit_default = ''


MSG_DEPRECATED_FIELD = """
{} does not exist in oTree. 
You should either replace it with one of oTree's field types, or import it from Django directly.
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


CASCADE = models.CASCADE
