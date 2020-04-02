from django.contrib import admin
from .models import (
    Session,
)


@admin.register(Session)
class SessionAdmin(admin.ModelAdmin):
    list_display = ['user_id', 'label']
