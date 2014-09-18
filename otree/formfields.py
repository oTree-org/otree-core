import babel
from django.conf import settings
import floppyforms.__future__ as forms


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


class MoneyField(forms.DecimalField):
    widget = MoneyInput

    def __init__(self, *args, **kwargs):
        kwargs.setdefault('widget', self.widget)
        super(MoneyField, self).__init__(*args, **kwargs)
