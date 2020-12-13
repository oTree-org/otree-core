from gettext import gettext
from typing import Dict
from otree import settings
import wtforms
import wtforms_sqlalchemy.orm
from sqlalchemy.types import Boolean
from wtforms import validators
from wtforms_sqlalchemy.orm import converts

import otree.common
import otree.constants
import otree.models
from otree.common import NON_FIELD_ERROR_KEY
from otree.currency import Currency, to_dec
from . import fields
from . import widgets


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


def bool_from_form_value(val):
    # when using test clients, we might get a non-string type
    if val in [None, False, '', '0', 'False']:
        return False
    return True


def get_choices_field(fa, is_currency=False, is_boolean=False):
    if is_boolean:
        fa.setdefault('choices', [(True, gettext('Yes')), (False, gettext('No'))])
        fa['coerce'] = bool_from_form_value
    if 'choices' in fa:
        if is_currency:
            before = fa['choices']
            if isinstance(before[0], (list, tuple)):
                after = [(to_dec(v), label) for (v, label) in before]
            else:
                after = [(to_dec(v), Currency(v)) for v in before]
            fa['choices'] = after
            fa['coerce'] = Currency

        widget = fa.pop('widget', None)
        if widget:
            widget = type(widget)
        return {
            widgets.RadioSelect: fields.RadioField,
            widgets.RadioSelectHorizontal: fields.RadioFieldHorizontal,
            widgets.TextInput: fields.StringField,
            None: fields.DropdownField,
        }[widget](**fa)


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
        return get_choices_field(field_args) or fields.StringField(**field_args)

    @converts("Integer")  # includes BigInteger and SmallInteger
    def handle_integer_types(self, model, column, field_args, **extra):
        unsigned = getattr(column.type, "unsigned", False)
        if unsigned:
            field_args["validators"].append(validators.NumberRange(min=0))
        return get_choices_field(field_args) or fields.IntegerField(**field_args)

    @converts("CurrencyType")
    def handle_currency(self, field_args, **extra):
        # override default decimal places limit, use database defaults instead
        return get_choices_field(field_args, is_currency=True) or fields.CurrencyField(
            **field_args
        )

    @converts("Text")
    def conv_Text(self, field_args, **extra):
        self._string_common(field_args=field_args, **extra)
        return fields.TextAreaField(**field_args)

    @converts("Boolean")
    def conv_Boolean(self, field_args, **extra):
        field_args.setdefault('widget', widgets.RadioSelect())
        fld = get_choices_field(field_args, is_boolean=True)
        return fld

    @converts("Numeric")  # includes DECIMAL, Float/FLOAT, REAL, and DOUBLE
    def handle_decimal_types(self, field_args, **extra):
        return get_choices_field(field_args) or fields.FloatField(**field_args)


class ModelForm(wtforms.Form):
    class Meta:
        # take first 2 chars because otherwise chinese has problems
        locales = [settings.LANGUAGE_CODE_ISO[:2]]

    _fields: Dict[str, wtforms.fields.Field]
    non_field_errors = None

    def __init__(
        self, view, formdata=None, obj=None, prefix='', data=None, meta=None, **kwargs,
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
        if not super().validate():
            return False
        ModelClass = type(self.instance)
        for name, field in self._fields.items():
            column = getattr(ModelClass, name)
            if (
                column.type == Boolean
                or isinstance(column.type, Boolean)
                and field.data is None
                and not column.form_props.get('blank')
            ):
                msg = otree.constants.field_required_msg
                field.errors.append(msg)

            error_message_method = self._get_method_from_page_or_model(
                f'{name}_error_message'
            )
            if error_message_method:
                try:
                    error_string = error_message_method(field.data)
                except:
                    raise  #  ResponseForException
                if error_string:
                    field.errors.append(error_string)

        if not self.errors and hasattr(self.view, 'error_message'):
            try:
                error = self.view.error_message(self.data)
            except:
                raise  #  ResponseForException
            if error:
                if isinstance(error, dict):
                    for k, v in error.items():
                        getattr(self, k).errors.append(v)
                else:
                    self.non_field_errors = error
        return not bool(self.errors or self.non_field_errors)

    @property
    def errors(self):
        errors = super().errors
        if self.non_field_errors:
            errors['__all__'] = self.non_field_errors
        return errors


def model_form(ModelClass, obj, only):
    field_args = {}

    for name in only:
        field_props = getattr(ModelClass, name).form_props

        wtf_props = {'validators': [], 'render_kw': {}}
        if 'label' in field_props:
            wtf_props['label'] = field_props['label']

        widget = field_props.get('widget')
        if widget:
            # actually we should deprecate passing widget instances since they are probably mutable
            if isinstance(widget, type):
                # wtforms expects widget instances
                widget = widget()
            wtf_props['widget'] = widget

        if hasattr(obj, f'{name}_min'):
            min = getattr(obj, f'{name}_min')()
        else:
            min = field_props.get('min')

        if hasattr(obj, f'{name}_max'):
            max = getattr(obj, f'{name}_max')()
        else:
            max = field_props.get('max')

        if [min, max] != [None, None]:
            wtf_props['validators'].append(validators.NumberRange(min=min, max=max))
        if min is not None:
            wtf_props['render_kw'].update(min=to_dec(min))
        if max is not None:
            wtf_props['render_kw'].update(max=to_dec(max))

        if not field_props.get('blank'):
            wtf_props['validators'].append(validators.InputRequired())

        wtf_props['description'] = field_props.get('help_text')

        if hasattr(obj, f'{name}_choices'):
            wtf_props['choices'] = getattr(obj, f'{name}_choices')()
        elif 'choices' in field_props:
            wtf_props['choices'] = field_props['choices']

        field_args[name] = wtf_props

    return wtforms_sqlalchemy.orm.model_form(
        model=ModelClass,
        base_class=ModelForm,
        only=only,
        converter=ModelConverter(),
        field_args=field_args,
    )


def get_form(instance, field_names, view, formdata):
    FormClass = model_form(type(instance), obj=instance, only=field_names)
    return FormClass(formdata=formdata, obj=instance, view=view)
