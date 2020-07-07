from decimal import Decimal

from django.conf import settings
from django.utils.encoding import force_text
from django.utils.translation import ugettext_lazy
from otree.currency import Currency, RealWorldCurrency
from django import forms

# TextInput could be useful if someone wants to set choices= but doesn't
# want a dropdown. Same for NumberInput actually. But they could also
# just use FOO_error_message, so they don't need to know the name of each input.
from django.forms.widgets import (
    CheckboxInput,
    HiddenInput,
    RadioSelect,
    TextInput,
    Textarea,
)  # noqa


def make_deprecated_widget(WidgetName):
    def DeprecatedWidget(*args, **kwargs):
        # putting the msg on a separate line gives better tracebacks
        msg = (
            f'{WidgetName} does not exist in oTree. You should either delete it, '
            f'or import it from Django directly.'
        )
        raise Exception(msg)

    return DeprecatedWidget


Media = make_deprecated_widget('Media')
MediaDefiningClass = make_deprecated_widget('MediaDefiningClass')
Widget = make_deprecated_widget('Widget')
NumberInput = make_deprecated_widget('NumberInput')
EmailInput = make_deprecated_widget('EmailInput')
URLInput = make_deprecated_widget('URLInput')
PasswordInput = make_deprecated_widget('PasswordInput')
MultipleHiddenInput = make_deprecated_widget('MultipleHiddenInput')
FileInput = make_deprecated_widget('FileInput')
ClearableFileInput = make_deprecated_widget('ClearableFileInput')
DateInput = make_deprecated_widget('DateInput')
DateTimeInput = make_deprecated_widget('DateTimeInput')
TimeInput = make_deprecated_widget('TimeInput')
Select = make_deprecated_widget('Select')
NullBooleanSelect = make_deprecated_widget('NullBooleanSelect')
SelectMultiple = make_deprecated_widget('SelectMultiple')
CheckboxSelectMultiple = make_deprecated_widget('CheckboxSelectMultiple')
MultiWidget = make_deprecated_widget('MultiWidget')
SplitDateTimeWidget = make_deprecated_widget('SplitDateTimeWidget')
SplitHiddenDateTimeWidget = make_deprecated_widget('SplitHiddenDateTimeWidget')
SelectDateWidget = make_deprecated_widget('SelectDateWidget')

from otree.currency.locale import CURRENCY_SYMBOLS


class _BaseMoneyInput(forms.NumberInput):
    # step = 0.01
    template_name = 'otree/forms/moneyinput.html'

    def get_context(self, *args, **kwargs):
        context = super().get_context(*args, **kwargs)
        context['currency_symbol'] = self.CURRENCY_SYMBOL
        return context

    def format_value(self, value):
        if isinstance(value, (Currency, RealWorldCurrency)):
            value = Decimal(value)
        return force_text(value)


class _RealWorldCurrencyInput(_BaseMoneyInput):
    '''it's a class attribute so take care with patching it in tests'''

    CURRENCY_SYMBOL = CURRENCY_SYMBOLS.get(
        settings.REAL_WORLD_CURRENCY_CODE, settings.REAL_WORLD_CURRENCY_CODE
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
    template_name = 'otree/forms/radio_select_horizontal.html'


class Slider(forms.NumberInput):
    input_type = 'range'
    template_name = 'otree/forms/slider.html'
    show_value = True

    def __init__(self, *args, show_value=None, **kwargs):
        try:
            # fix bug where currency "step" values were ignored.
            step = kwargs['attrs']['step']
            kwargs['attrs']['step'] = self.format_value(step)
        except KeyError:
            pass
        if show_value is not None:
            self.show_value = show_value
        super().__init__(*args, **kwargs)

    def format_value(self, value):
        if isinstance(value, (Currency, RealWorldCurrency)):
            value = Decimal(value)
        return force_text(value)

    def get_context(self, *args, **kwargs):
        context = super().get_context(*args, **kwargs)
        context['show_value'] = self.show_value
        return context


class SliderInput(Slider):
    '''old name for Slider widget'''

    pass
