import floppyforms.__future__ as forms
import otree.widgets


default_choices = (
    ('john', 'John'),
    ('suzanne', 'Suzanne'),
    ('one', 'One'),
    ('1', '$1.00'),
    ('2', '2'),
)


class WidgetDemoForm(forms.Form):
    radio_select = forms.ChoiceField(
        choices=default_choices,
        widget=otree.widgets.RadioSelect)
    radio_select_horizontal = forms.ChoiceField(
        choices=default_choices,
        widget=otree.widgets.RadioSelectHorizontal)
    checkbox_select = forms.MultipleChoiceField(
        choices=default_choices,
        widget=otree.widgets.CheckboxSelectMultiple)
    checkbox_select_horizontal = forms.MultipleChoiceField(
        choices=default_choices,
        widget=otree.widgets.CheckboxSelectMultipleHorizontal)
