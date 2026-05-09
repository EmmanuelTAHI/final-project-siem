from django.contrib import admin
from .models import Playbook, PlaybookExecution


@admin.register(Playbook)
class PlaybookAdmin(admin.ModelAdmin):
    list_display = ["name", "trigger_type", "is_active", "execution_count", "created_at"]
    list_filter = ["trigger_type", "is_active"]
    search_fields = ["name"]


@admin.register(PlaybookExecution)
class PlaybookExecutionAdmin(admin.ModelAdmin):
    list_display = ["playbook", "alert", "status", "triggered_by", "started_at"]
    list_filter = ["status", "triggered_by"]
    readonly_fields = ["actions_taken"]
