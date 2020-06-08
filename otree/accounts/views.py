import vanilla
from django.shortcuts import redirect
from django.contrib.auth.views import (
    LoginView, PasswordResetView, PasswordResetDoneView, PasswordResetConfirmView, PasswordResetCompleteView,
    LogoutView
)
from .forms import RegisterForm
from django.contrib.auth.forms import ReadOnlyPasswordHashField


class RegisterView(vanilla.FormView):
    form_class = RegisterForm
    success_url = '/accounts/login/'
    template_name = 'otree/accounts/register.html'

    def form_valid(self, form):
        form.save()
        return redirect('/accounts/login/')


class Login(LoginView):
    template_name = 'otree/accounts/login.html'


class ResetPassword(PasswordResetView):
    template_name = 'otree/accounts/reset_password.html'
    email_template_name = 'otree/accounts/reset_password_email.html'
    success_url = '/accounts/reset-password/done/'


class ResetPasswordDone(PasswordResetDoneView):
    template_name = 'otree/accounts/reset_password_done.html'


class ResetPasswordConfirm(PasswordResetConfirmView):
    template_name = 'otree/accounts/reset_password_confirm.html'
    success_url = '/accounts/reset-password/complete/'


class ResetPasswordComplete(PasswordResetCompleteView):
    template_name = 'otree/accounts/reset_password_complete.html'