
from .models import Player, Link
from django.forms import inlineformset_factory
from django import forms
from django import forms
from django.contrib.auth.forms import UserCreationForm
from django.contrib.auth.models import User


class RegisterForm(UserCreationForm):
    email = forms.EmailField()

    class Meta:
        model = User
        fields = ["username", "password1"]


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


