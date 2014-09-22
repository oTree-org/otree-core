import floppyforms.__future__ as forms
import otree.widgets


class MoneyField(forms.DecimalField):
    widget = otree.widgets.MoneyInput

    def __init__(self, *args, **kwargs):
        kwargs.setdefault('widget', self.widget)
        super(MoneyField, self).__init__(*args, **kwargs)
