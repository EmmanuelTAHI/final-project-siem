from django.contrib import admin
from .models import HuntingQuery, HuntingResult


@admin.register(HuntingQuery)
class HuntingQueryAdmin(admin.ModelAdmin):
    list_display = ["name", "mitre_tactic", "run_count", "last_results_count", "created_by"]
    search_fields = ["name", "description"]


@admin.register(HuntingResult)
class HuntingResultAdmin(admin.ModelAdmin):
    list_display = ["query", "log", "executed_at"]
    raw_id_fields = ["log"]
