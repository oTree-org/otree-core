



"""
class LinkForm(forms.ModelForm):
    class Meta:
        model = Link
        fields = ['edge']

    edge = forms.BooleanField(widget=forms.CheckboxInput, required=False)


LinkFormset = inlineformset_factory(Player, Link,
                                    form=LinkForm,
                                    extra=0,
                                    can_delete=False,
                                    fk_name='source',
                                    fields=['edge'])

"""
