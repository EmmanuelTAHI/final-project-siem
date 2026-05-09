from django.contrib import admin

from .models import CorrelationRule, RuleMatch


@admin.register(CorrelationRule)
class CorrelationRuleAdmin(admin.ModelAdmin):
    list_display = ("name", "severity", "is_active", "mitre_tactic", "created_at")
    list_filter = ("severity", "is_active", "mitre_tactic")
    search_fields = ("name", "description")
    ordering = ("name",)
    readonly_fields = ("id", "created_at", "updated_at")


@admin.register(RuleMatch)
class RuleMatchAdmin(admin.ModelAdmin):
    list_display = ("rule", "alert", "matched_at")
    list_filter = ("rule",)
    ordering = ("-matched_at",)
    readonly_fields = ("id", "matched_at")
