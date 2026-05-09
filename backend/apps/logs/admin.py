from django.contrib import admin

from .models import NormalizedLog, RawLog


@admin.register(RawLog)
class RawLogAdmin(admin.ModelAdmin):
    list_display = ("id", "source_type", "connector", "is_normalized", "received_at")
    list_filter = ("source_type", "is_normalized")
    search_fields = ("id",)
    ordering = ("-received_at",)
    readonly_fields = ("id", "received_at")


@admin.register(NormalizedLog)
class NormalizedLogAdmin(admin.ModelAdmin):
    list_display = (
        "id", "source_type", "action", "outcome", "severity",
        "user_email", "source_ip", "geo_country", "event_time"
    )
    list_filter = ("source_type", "action", "outcome", "severity")
    search_fields = ("user_email", "source_ip", "action")
    ordering = ("-event_time",)
    readonly_fields = ("id", "indexed_at")
