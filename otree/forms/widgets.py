from decimal import Decimal

from django.conf import settings
from django.utils.encoding import force_text
from django.utils.translation import ugettext_lazy
from otree.currency import Currency, RealWorldCurrency
import floppyforms.__future__ as forms
import floppyforms.widgets
from otree.currency.locale import CURRENCY_SYMBOLS

__all__ = (
    '_BaseMoneyInput',
    'CheckboxInput',
    'ClearableFileInput', 'ColorInput',
    '_CurrencyInput', 'DateInput', 'DateTimeInput', 'EmailInput', 'FileInput',
    'HiddenInput', 'IPAddressInput', 'Input', '_RealWorldCurrencyInput',
    'NullBooleanSelect', 'NumberInput', 'PasswordInput',
    'PhoneNumberInput', 'RadioSelect', 'RadioSelectHorizontal', 'RangeInput',
    'SearchInput', 'Select', 'SelectDateWidget',
    'SliderInput', 'SlugInput', 'SplitDateTimeWidget',
    'SplitHiddenDateTimeWidget', 'TextInput', 'Textarea', 'TimeInput',
    'URLInput', 'Widget',
)


Widget = floppyforms.widgets.Widget
Input = floppyforms.widgets.Input
TextInput = floppyforms.widgets.TextInput
PasswordInput = floppyforms.widgets.PasswordInput
HiddenInput = floppyforms.widgets.HiddenInput
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
RadioSelect = floppyforms.widgets.RadioSelect
SplitDateTimeWidget = floppyforms.widgets.SplitDateTimeWidget
SplitHiddenDateTimeWidget = floppyforms.widgets.SplitHiddenDateTimeWidget
SelectDateWidget = floppyforms.widgets.SelectDateWidget

# don't use Multiple widgets because they don't correspond to any model field
# CheckboxSelectMultiple = floppyforms.widgets.CheckboxSelectMultiple
# MultiWidget = floppyforms.widgets.MultiWidget
# SelectMultiple = floppyforms.widgets.SelectMultiple
# MultipleHiddenInput = floppyforms.widgets.MultipleHiddenInput
# class CheckboxSelectMultipleHorizontal(forms.CheckboxSelectMultiple):
#    template_name = 'floppyforms/checkbox_select_horizontal.html'


class _BaseMoneyInput(forms.NumberInput):
    # step = 0.01
    template_name = 'floppyforms/moneyinput.html'

    def get_context(self, *args, **kwargs):
        context = super(_BaseMoneyInput, self).get_context(*args, **kwargs)
        context['currency_symbol'] = self.CURRENCY_SYMBOL
        return context

    def _format_value(self, value):
        if isinstance(value, (Currency, RealWorldCurrency)):
            value = Decimal(value)
        return force_text(value)


class _RealWorldCurrencyInput(_BaseMoneyInput):
    '''it's a class attribute so take care with patching it in tests'''
    CURRENCY_SYMBOL = CURRENCY_SYMBOLS.get(
        settings.REAL_WORLD_CURRENCY_CODE,
        settings.REAL_WORLD_CURRENCY_CODE,
    )


class _CurrencyInput(_RealWorldCurrencyInput):
    '''it's a class attribute so take care with patching it in tests'''
    if settings.USE_POINTS:
        if hasattr(settings, 'POINTS_CUSTOM_NAME'):
            CURRENCY_SYMBOL = settings.POINTS_CUSTOM_NAME
        else:
            # Translators: the label next to a "points" input field
            CURRENCY_SYMBOL = ugettext_lazy('points')


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

    def _format_value(self, value):
        if isinstance(value, (Currency, RealWorldCurrency)):
            value = Decimal(value)
        return force_text(value)

    def get_context(self, *args, **kwargs):
        context = super(SliderInput, self).get_context(*args, **kwargs)
        context['show_value'] = self.show_value
        return context
