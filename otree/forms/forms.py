import enum
from typing import Dict

import wtforms
import wtforms_sqlalchemy.orm
from sqlalchemy.sql import sqltypes as st
from sqlalchemy.types import Boolean
from wtforms import validators
from wtforms_sqlalchemy.orm import converts

import otree.common
import otree.constants
import otree.models
from otree import settings
from otree.currency import Currency, to_dec
from otree.database import CurrencyType
from . import fields
from . import widgets
from ..i18n import core_gettext


def model_form(ModelClass, obj, only):
    field_args = {}

    for name in only:
        model_field = getattr(ModelClass, name)
        field_props = model_field.form_props

        # fa = field_args
        fa = {
            'validators': [],
            'render_kw': {},
            # to match Django behavior
            'id': f'id_{name}',
        }
        if 'label' in field_props:
            fa['label'] = field_props['label']

        target = obj.get_user_defined_target()

        func = getattr(target, f'{name}_choices', None)
        has_choices = False
        if func:
            fa['choices'] = func(obj)
            has_choices = True
        elif 'choices' in field_props:
            fa['choices'] = field_props['choices']
            has_choices = True

        if not has_choices and type(model_field.type) in [
            st.Integer,
            st.Float,
            CurrencyType,
        ]:

            func = getattr(target, f'{name}_min', None)
            if func:
                min = func(obj)
            else:
                # 0 is the default, not None
                min = field_props.get('min', 0)

            func = getattr(target, f'{name}_max', None)
            if func:
                max = func(obj)
            else:
                max = field_props.get('max')

            if [min, max] != [None, None]:
                fa['validators'].append(validators.NumberRange(min=min, max=max))
            if min is not None:
                fa['render_kw'].update(min=to_dec(min))
            if max is not None:
                fa['render_kw'].update(max=to_dec(max))

        if not field_props.get('blank'):
            fa['validators'].append(validators.InputRequired())

        fa['description'] = field_props.get('help_text')

        widget = field_props.get('widget')
        if widget:
            # actually we should deprecate passing widget instances since they are probably mutable
            if isinstance(widget, type):
                # wtforms expects widget instances
                widget = widget()
            fa['widget'] = widget
        field_args[name] = fa

    return wtforms_sqlalchemy.orm.model_form(
        model=ModelClass,
        base_class=ModelForm,
        only=only,
        converter=ModelConverter(),
        field_args=field_args,
    )


def get_form(instance, field_names, view, formdata):
    instance._is_frozen = False

    FormClass = model_form(type(instance), obj=instance, only=field_names)
    form = FormClass(formdata=formdata, obj=instance, view=view)
    # because only= does not preserve order, so we need to store this
    # so that {{ formfields }} tag can access it.
    form.field_names = field_names
    instance._is_frozen = True
    return form


class ModelConverter(wtforms_sqlalchemy.orm.ModelConverterBase):
    def __init__(self, extra_converters=None, use_mro=True):
        super().__init__(extra_converters, use_mro=use_mro)

    @classmethod
    def _string_common(cls, column, field_args, **extra):
        if isinstance(column.type.length, int) and column.type.length:
            field_args["validators"].append(validators.Length(max=column.type.length))

    @converts("String")  # includes Unicode
    def conv_String(self, field_args, **extra):
        self._string_common(field_args=field_args, **extra)
        return get_choices_field(field_args, FormDataTypes.str) or fields.StringField(
            **field_args
        )

    @converts("Text")
    def conv_Text(self, field_args, **extra):
        self._string_common(field_args=field_args, **extra)
        return fields.TextAreaField(**field_args)

    @converts("Boolean")
    def conv_Boolean(self, field_args, **extra):
        field_args.setdefault('widget', widgets.RadioSelect())
        if isinstance(field_args['widget'], widgets.CheckboxInput):
            return fields.CheckboxField(**field_args)
        fld = get_choices_field(field_args, FormDataTypes.bool)
        return fld

    @converts("Integer")  # includes BigInteger and SmallInteger
    def handle_integer_types(self, model, column, field_args, **extra):
        unsigned = getattr(column.type, "unsigned", False)
        if unsigned:
            field_args["validators"].append(validators.NumberRange(min=0))
        return get_choices_field(field_args, FormDataTypes.int) or fields.IntegerField(
            **field_args
        )

    @converts("Numeric")  # includes DECIMAL, Float/FLOAT, REAL, and DOUBLE
    def handle_decimal_types(self, field_args, **extra):
        return get_choices_field(field_args, FormDataTypes.float) or fields.FloatField(
            **field_args,
        )

    @converts("CurrencyType")
    def handle_currency(self, field_args, **extra):
        return get_choices_field(
            field_args, FormDataTypes.Currency
        ) or fields.CurrencyField(**field_args)


def bool_from_form_value(val):
    # when using test clients, we might get a non-string type
    # javascript uses 'false'
    if val in [None, False, '', '0', 'False', 'false']:
        return False
    return True


class FormDataTypes(enum.Enum):
    bool = 'bool'
    float = 'float'
    int = 'int'
    Currency = 'currency'
    str = 'str'


coerce_functions = {
    FormDataTypes.bool: bool_from_form_value,
    FormDataTypes.int: int,
    FormDataTypes.float: float,
    FormDataTypes.Currency: Currency,
    FormDataTypes.str: str,
}


def get_choices_field(fa, datatype: FormDataTypes):
    # fa means field_args
    if datatype == FormDataTypes.bool:

        fa.setdefault(
            'choices', [(True, core_gettext('Yes')), (False, core_gettext('No'))]
        )
    if 'choices' in fa:
        if datatype == FormDataTypes.Currency:
            before = fa['choices']
            if isinstance(before[0], (list, tuple)):
                after = [(to_dec(v), label) for (v, label) in before]
            else:
                after = [(to_dec(v), Currency(v)) for v in before]
            fa['choices'] = after
        fa['coerce'] = coerce_functions[datatype]

        widget = fa.pop('widget', None)
        if widget:
            widget = type(widget)
        return {
            widgets.RadioSelect: fields.RadioField,
            widgets.RadioSelectHorizontal: fields.RadioFieldHorizontal,
            widgets.TextInput: fields.StringField,
            None: fields.DropdownField,
        }[widget](**fa)
    elif fa.get('widget') and isinstance(
        fa['widget'], (widgets.RadioSelect, widgets.RadioSelectHorizontal)
    ):
        msg = f'Field uses a radio/select widget but no choices are defined'
        raise Exception(msg)


class ModelForm(wtforms.Form):
    class Meta:
        # take first 2 chars because otherwise chinese has problems
        locales = [settings.LANGUAGE_CODE_ISO[:2]]

    _fields: Dict[str, wtforms.fields.Field]
    non_field_error = None
    field_names = []

    def __init__(
        self,
        view,
        formdata=None,
        obj=None,
        prefix='',
        data=None,
        meta=None,
        **kwargs,
    ):
        self.view = view
        self.instance = obj

        super().__init__(
            formdata=formdata, obj=obj, prefix=prefix, data=data, meta=meta, **kwargs
        )

    def _get_method_from_page_or_model(self, method_name):
        for obj in [self.view, self.instance]:
            if hasattr(obj, method_name):
                meth = getattr(obj, method_name)
                if callable(meth):
                    return meth

    def validate(self):
        super_validates = super().validate()
        # even if super doesn't validate,
        # we don't return False right away, because we want to validate all fields
        # individually at once.
        # this is useful e.g. for showing error messages in the UI, and SubmissionMustFail(error_fields=...)
        # i think i remember that calculating form.errors was slow, so avoid if possible.
        fields_with_errors = [] if super_validates else list(self.errors)
        ModelClass = type(self.instance)
        for name, field in self._fields.items():
            if name in fields_with_errors:
                continue

            column = getattr(ModelClass, name)
            if (
                column.type == Boolean
                or isinstance(column.type, Boolean)
                and field.data is None
                and not column.form_props.get('blank')
            ):
                msg = otree.constants.field_required_msg
                field.errors.append(msg)

            error_string = self.instance.call_user_defined(
                f'{name}_error_message', field.data, missing_ok=True
            )
            if error_string:
                field.errors.append(error_string)

        if not self.errors and hasattr(self.view, 'error_message'):
            error = self.view.call_user_defined('error_message', self.data)
            if error:
                if isinstance(error, dict):
                    for k, v in error.items():
                        getattr(self, k).errors.append(v)
                else:
                    self.non_field_error = error
        return not bool(self.errors or self.non_field_error)

    @property
    def errors(self):
        errors = super().errors
        if self.non_field_error:
            errors['__all__'] = self.non_field_error
        return errors

    def __iter__(self):
        return (self[k] for k in self.field_names)


def expand_choice_tuples(choices):
    '''
    Don't need it while generating the form,
    since wtforms also accepts flat lists.
    '''
    if not choices:
        return None
    if not isinstance(choices[0], (list, tuple)):
        choices = [(value, value) for value in choices]
    return choices
