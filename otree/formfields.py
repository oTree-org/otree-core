import floppyforms.__future__ as forms
import otree.widgets
from easymoney import to_dec


__all__ = ('MoneyField', 'MoneyChoiceField',)


class MoneyField(forms.DecimalField):
    widget = otree.widgets.MoneyInput

    def __init__(self, *args, **kwargs):
        kwargs.setdefault('widget', self.widget)
        super(MoneyField, self).__init__(*args, **kwargs)


class MoneyChoiceField(forms.TypedChoiceField):
    def __init__(self, *args, **kwargs):
        super(MoneyChoiceField, self).__init__(*args, **kwargs)
        self.choices = [(to_dec(k), v) for k, v in self.choices]

    def prepare_value(self, value):
        return to_dec(value)
