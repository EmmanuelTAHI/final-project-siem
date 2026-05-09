from django.contrib import admin
from django.contrib.auth.admin import UserAdmin

from .models import AuditTrail, User


@admin.register(User)
class LogPlusUserAdmin(UserAdmin):
    list_display = ("email", "first_name", "last_name", "role", "is_active", "created_at")
    list_filter = ("role", "is_active")
    search_fields = ("email", "first_name", "last_name")
    ordering = ("-created_at",)
    fieldsets = (
        (None, {"fields": ("email", "password")}),
        ("Informations personnelles", {"fields": ("first_name", "last_name")}),
        ("Rôle & Permissions", {"fields": ("role", "is_active", "is_staff", "is_superuser")}),
        ("Dates", {"fields": ("last_login", "date_joined")}),
    )
    add_fieldsets = (
        (
            None,
            {
                "classes": ("wide",),
                "fields": ("email", "first_name", "last_name", "role", "password1", "password2"),
            },
        ),
    )


@admin.register(AuditTrail)
class AuditTrailAdmin(admin.ModelAdmin):
    list_display = ("timestamp", "user", "action", "target_model", "ip_address")
    list_filter = ("action", "target_model")
    search_fields = ("user__email", "action", "target_model", "ip_address")
    ordering = ("-timestamp",)
    readonly_fields = ("id", "timestamp")
