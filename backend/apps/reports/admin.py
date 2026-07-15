from django.contrib import admin

from .models import GeneratedReport


@admin.register(GeneratedReport)
class GeneratedReportAdmin(admin.ModelAdmin):
    list_display = ("label", "report_type", "format", "organization", "requested_by", "created_at")
    list_filter = ("report_type", "format", "organization")
    search_fields = ("label", "requested_by__email")
    readonly_fields = [f.name for f in GeneratedReport._meta.fields]
