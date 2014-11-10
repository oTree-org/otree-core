from otree import forms
from otree.common import currency_range


default_choices = (
    ('john', 'John'),
    ('suzanne', 'Suzanne'),
    ('one', 'One'),
    ('1', '$1.00'),
    ('2', '2'),
)


class WidgetDemoForm(forms.Form):
    char = forms.CharField(required=False)

    text = forms.CharField(required=False, widget=forms.Textarea)

    radio_select = forms.ChoiceField(
        choices=default_choices,
        widget=forms.RadioSelect)
    radio_select_horizontal = forms.ChoiceField(
        choices=default_choices,
        widget=forms.RadioSelectHorizontal)
    checkbox_select = forms.MultipleChoiceField(
        choices=default_choices,
        widget=forms.CheckboxSelectMultiple)
    checkbox_select_horizontal = forms.MultipleChoiceField(
        choices=default_choices,
        widget=forms.CheckboxSelectMultipleHorizontal)

    currency = forms.CurrencyField()
    currency_choice = forms.CurrencyChoiceField(choices=[(m, m) for m in currency_range(0,0.75, 0.05)])
