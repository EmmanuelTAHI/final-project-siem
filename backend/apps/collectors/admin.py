from django.contrib import admin

from .models import CollectionJob, ConnectorConfig


@admin.register(ConnectorConfig)
class ConnectorConfigAdmin(admin.ModelAdmin):
    list_display = ("name", "source_type", "is_active", "last_collected_at", "created_at")
    list_filter = ("source_type", "is_active")
    search_fields = ("name",)
    readonly_fields = ("id", "created_at", "credentials_encrypted")
    ordering = ("-created_at",)


@admin.register(CollectionJob)
class CollectionJobAdmin(admin.ModelAdmin):
    list_display = ("connector", "status", "logs_collected_count", "started_at", "finished_at")
    list_filter = ("status", "connector")
    ordering = ("-started_at",)
    readonly_fields = ("id",)
