from django.contrib import admin
from .models import EnrichedLog, ThreatIndicator


@admin.register(ThreatIndicator)
class ThreatIndicatorAdmin(admin.ModelAdmin):
    list_display = ["indicator_type", "value", "reputation_score", "source", "is_malicious", "last_seen"]
    list_filter = ["indicator_type", "source", "is_malicious"]
    search_fields = ["value"]
    ordering = ["-reputation_score"]


@admin.register(EnrichedLog)
class EnrichedLogAdmin(admin.ModelAdmin):
    list_display = ["log", "max_score", "is_threat", "enriched_at"]
    list_filter = ["is_threat"]
