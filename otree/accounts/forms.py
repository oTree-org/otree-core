from django import forms
from django.contrib.auth.forms import UserCreationForm, AuthenticationForm
from otree.models_concrete import User
from django.contrib.auth.hashers import BCryptSHA256PasswordHasher, make_password


class RegisterForm(UserCreationForm):
    email = forms.EmailField(required=True)

    class Meta:
        model = User
        fields = ('email', 'password1', 'password2')

    def save(self, commit=True):
        user = super(UserCreationForm, self).save(commit=False)
        user.email = self.cleaned_data['email']
        user.password = make_password(self.cleaned_data['password1'])

        if commit:
            user.save()
            print("User saved")
        return user


class LoginForm(AuthenticationForm):
    username = forms.EmailField(required=True)
