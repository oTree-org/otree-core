from decimal import Decimal

from babel.core import Locale
from django.conf import settings
import babel
import babel.numbers
import easymoney
import floppyforms.__future__ as forms
import floppyforms.widgets


__all__ = (
    'BaseMoneyInput', 'CheckboxInput', 'CheckboxSelectMultiple',
    'CheckboxSelectMultipleHorizontal', 'ClearableFileInput', 'ColorInput',
    'CurrencyInput', 'DateInput', 'DateTimeInput', 'EmailInput', 'FileInput',
    'HiddenInput', 'IPAddressInput', 'Input', 'CurrencyInput', 'CurrencyInput',
    'MultiWidget',
    'MultipleHiddenInput', 'NullBooleanSelect', 'NumberInput', 'PasswordInput',
    'PhoneNumberInput', 'RadioSelect', 'RadioSelectHorizontal', 'RangeInput',
    'SearchInput', 'Select', 'SelectDateWidget', 'SelectMultiple',
    'SliderInput', 'SlugInput', 'SplitDateTimeWidget',
    'SplitHiddenDateTimeWidget', 'TextInput', 'Textarea', 'TimeInput',
    'URLInput', 'Widget',
)


Widget = floppyforms.widgets.Widget
Input = floppyforms.widgets.Input
TextInput = floppyforms.widgets.TextInput
PasswordInput = floppyforms.widgets.PasswordInput
HiddenInput = floppyforms.widgets.HiddenInput
MultipleHiddenInput = floppyforms.widgets.MultipleHiddenInput
SlugInput = floppyforms.widgets.SlugInput
IPAddressInput = floppyforms.widgets.IPAddressInput
FileInput = floppyforms.widgets.FileInput
ClearableFileInput = floppyforms.widgets.ClearableFileInput
Textarea = floppyforms.widgets.Textarea
DateInput = floppyforms.widgets.DateInput
DateTimeInput = floppyforms.widgets.DateTimeInput
TimeInput = floppyforms.widgets.TimeInput
SearchInput = floppyforms.widgets.SearchInput
EmailInput = floppyforms.widgets.EmailInput
URLInput = floppyforms.widgets.URLInput
ColorInput = floppyforms.widgets.ColorInput
NumberInput = floppyforms.widgets.NumberInput
RangeInput = floppyforms.widgets.RangeInput
PhoneNumberInput = floppyforms.widgets.PhoneNumberInput
CheckboxInput = floppyforms.widgets.CheckboxInput
Select = floppyforms.widgets.Select
NullBooleanSelect = floppyforms.widgets.NullBooleanSelect
SelectMultiple = floppyforms.widgets.SelectMultiple
RadioSelect = floppyforms.widgets.RadioSelect
CheckboxSelectMultiple = floppyforms.widgets.CheckboxSelectMultiple
MultiWidget = floppyforms.widgets.MultiWidget
SplitDateTimeWidget = floppyforms.widgets.SplitDateTimeWidget
SplitHiddenDateTimeWidget = floppyforms.widgets.SplitHiddenDateTimeWidget
SelectDateWidget = floppyforms.widgets.SelectDateWidget


class CheckboxSelectMultipleHorizontal(forms.CheckboxSelectMultiple):
    template_name = 'floppyforms/checkbox_select_horizontal.html'


class BaseMoneyInput(forms.NumberInput):
    step = '0.01'
    template_name = 'floppyforms/moneyinput.html'

    def get_currency_symbol(self, currency_code):
        return babel.numbers.get_currency_symbol(
            currency_code, self.currency_locale)

    def get_context(self, *args, **kwargs):
        context = super(BaseMoneyInput, self).get_context(*args, **kwargs)
        currency_symbol = self.get_currency_symbol(self.currency_code)
        context.setdefault('currency', self.currency_code)
        context.setdefault('currency_symbol', currency_symbol)
        context['currency_symbol_is_prefix'] = self.currency_symbol_is_prefix()
        return context

    def currency_symbol_is_prefix(self):
        if settings.USE_POINTS:
            return False
        locale = Locale.parse(self.currency_locale)
        format = locale.currency_formats.get(None)
        pattern = babel.numbers.parse_pattern(format)
        return u'\xa4' in pattern.prefix[0]

    def _format_value(self, value):
        if isinstance(value, easymoney.Money):
            return Decimal(value)
        return value


class RealWorldCurrencyInput(BaseMoneyInput):
    currency_code = settings.REAL_WORLD_CURRENCY_CODE
    currency_locale = settings.REAL_WORLD_CURRENCY_LOCALE
    currency_format = settings.REAL_WORLD_CURRENCY_FORMAT


class CurrencyInput(BaseMoneyInput):
    currency_code = settings.GAME_CURRENCY_CODE
    currency_locale = settings.GAME_CURRENCY_LOCALE
    currency_format = settings.GAME_CURRENCY_FORMAT


class RadioSelectHorizontal(forms.RadioSelect):
    template_name = 'floppyforms/radio_select_horizontal.html'


class SliderInput(forms.RangeInput):
    template_name = 'floppyforms/slider.html'
    show_value = True

    def __init__(self, *args, **kwargs):
        show_value = kwargs.pop('show_value', None)
        if show_value is not None:
            self.show_value = show_value
        super(SliderInput, self).__init__(*args, **kwargs)

    def get_context(self, *args, **kwargs):
        context = super(SliderInput, self).get_context(*args, **kwargs)
        context['show_value'] = self.show_value
        return context
