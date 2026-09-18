from django.contrib import admin
from django.contrib.auth.admin import UserAdmin
from .models import User

@admin.register(User)
class UserAdmin(UserAdmin):
    fieldsets = UserAdmin.fieldsets + (('Дополнительная информация', {'fields': ('phone', 'city', 'avatar')}),)
    list_display = ('username', 'email', 'phone', 'city', 'avatar','is_staff')