from . import widgets as wg
import wtforms.fields as wtfields
from otree.currency import Currency, RealWorldCurrency, to_dec


class StringField(wtfields.StringField):
    widget = wg.TextInput()


class IntegerField(wtfields.IntegerField):
    widget = wg.NumberWidget(step='1')


class FloatField(wtfields.FloatField):
    widget = wg.NumberWidget(step='0.0001')


class RadioField(wtfields.RadioField):
    widget = wg.RadioSelect()
    option_widget = wg.RadioOption()


class RadioFieldHorizontal(wtfields.RadioField):
    widget = wg.RadioSelectHorizontal()
    option_widget = wg.RadioOption()


class DropdownField(wtfields.SelectField):
    widget = wg.Dropdown()
    option_widget = wg.DropdownOption()


class CurrencyField(wtfields.Field):
    widget = wg.CurrencyWidget()

    def process_formdata(self, valuelist):
        if valuelist and valuelist[0]:
            data = Currency(valuelist[0])
        else:
            data = None
        self.data = data

    def _value(self):
        if self.data is None:
            return ''
        return str(to_dec(self.data))


class TextAreaField(StringField):
    """
    This field represents an HTML ``<textarea>`` and can be used to take
    multi-line input.
    """

    widget = wg.TextArea()


