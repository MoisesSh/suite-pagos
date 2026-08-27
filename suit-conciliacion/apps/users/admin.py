from django.contrib import admin
from django.contrib.auth.admin import UserAdmin

from apps.users.domain.models import Usuario


@admin.register(Usuario)
class UsuarioAdmin(UserAdmin):
    ordering = ['email']
    list_display = ['email', 'username', 'is_staff', 'is_superuser', 'is_active']
    search_fields = ['email', 'username']
