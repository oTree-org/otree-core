import decimal
import wtforms.fields as wtfields
from otree.currency import Currency, to_dec
from otree.i18n import format_number

from . import widgets as wg


def handle_localized_number_input(val):
    if val is None:
        return val
    return val.replace(',', '.')


class FloatField(wtfields.FloatField):
    widget = wg.FloatWidget()

    def process_formdata(self, valuelist):
        if valuelist:
            try:
                self.data = float(handle_localized_number_input(valuelist[0]))
            except ValueError:
                self.data = None
                raise ValueError(self.gettext('Not a valid float value'))

    def _value(self):
        if self.data is None:
            return ''
        return format_number(self.data)


class CurrencyField(wtfields.Field):
    widget = wg.CurrencyWidget()

    def process_formdata(self, valuelist):
        if valuelist and valuelist[0]:
            try:
                data = Currency(handle_localized_number_input(valuelist[0]))
            except (decimal.InvalidOperation, ValueError):
                self.data = None
                raise ValueError(self.gettext('Not a valid decimal value'))
        else:
            data = None
        self.data = data

    def _value(self):
        if self.data is None:
            return ''
        return format_number(to_dec(self.data))


class StringField(wtfields.StringField):
    widget = wg.TextInput()


class IntegerField(wtfields.IntegerField):
    widget = wg.IntegerWidget()


class RadioField(wtfields.RadioField):
    widget = wg.RadioSelect()
    option_widget = wg.RadioOption()


class RadioFieldHorizontal(wtfields.RadioField):
    widget = wg.RadioSelectHorizontal()
    option_widget = wg.RadioOption()


class DropdownField(wtfields.SelectField):
    widget = wg.Select()
    option_widget = wg.SelectOption()


class TextAreaField(StringField):
    """
    This field represents an HTML ``<textarea>`` and can be used to take
    multi-line input.
    """

    widget = wg.TextArea()


class CheckboxField(wtfields.BooleanField):
    widget = wg.CheckboxInput()
