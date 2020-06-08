from django.conf.urls import url, include
from django.contrib.auth.views import (
    LogoutView, PasswordResetView, PasswordResetDoneView, PasswordResetConfirmView,
    PasswordResetCompleteView
)
from . import views
from django.contrib.auth import logout


urlpatterns = [
    url(r'^login/$', views.Login.as_view(), name='login'),
    url(r'^logout/$', logout, name='logout'),
    url(r'^register/$', views.RegisterView.as_view(), name='register'),
    url(r'^reset-password/$', views.ResetPassword.as_view(), name='reset_password'),
    url(r'^reset-password/done/$', views.ResetPasswordDone.as_view(), name='password_reset_done'),
    url(r'^reset-password/confirm/(?P<uidb64>[0-9A-Za-z]+)-(?P<token>.+)/$', views.ResetPasswordConfirm.as_view(),
        name='password_reset_confirm'),
    url(r'^reset-password/complete/$', views.ResetPasswordComplete.as_view(), name='password'),
]
