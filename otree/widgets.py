import babel
from django.conf import settings
import floppyforms.__future__ as forms
import floppyforms.widgets


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


class MoneyInput(forms.NumberInput):
    currency_code = getattr(settings, 'CURRENCY_CODE', 'USD')
    step = '0.05'
    template_name = 'floppyforms/moneyinput.html'

    def __init__(self, *args, **kwargs):
        self.currency_code = kwargs.pop('currency_code', None) or self.currency_code
        super(MoneyInput, self).__init__(*args, **kwargs)

    def get_currency_symbol(self, currency_code):
        return babel.numbers.get_currency_symbol(
            currency_code, settings.CURRENCY_LOCALE)

    def get_context(self, *args, **kwargs):
        context = super(MoneyInput, self).get_context(*args, **kwargs)
        currency_symbol = self.get_currency_symbol(self.currency_code)
        context.setdefault('currency', self.currency_code)
        context.setdefault('currency_symbol', currency_symbol)
        return context


class RadioSelectHorizontal(forms.RadioSelect):
    template_name = 'floppyforms/radio_select_horizontal.html'
