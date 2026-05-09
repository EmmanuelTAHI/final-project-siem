from django.contrib import admin

from .models import Alert, AlertComment


@admin.register(Alert)
class AlertAdmin(admin.ModelAdmin):
    list_display = ("title", "severity", "status", "assigned_to", "rule", "created_at")
    list_filter = ("severity", "status", "rule")
    search_fields = ("title", "description")
    ordering = ("-created_at",)
    readonly_fields = ("id", "created_at", "updated_at")


@admin.register(AlertComment)
class AlertCommentAdmin(admin.ModelAdmin):
    list_display = ("alert", "author", "created_at")
    ordering = ("-created_at",)
    readonly_fields = ("id", "created_at")
