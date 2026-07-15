from rest_framework import serializers

from .models import GeneratedReport


class GeneratedReportSerializer(serializers.ModelSerializer):
    requested_by_name = serializers.CharField(source="requested_by.full_name", default="", read_only=True)
    report_type_label = serializers.CharField(source="get_report_type_display", read_only=True)

    class Meta:
        model = GeneratedReport
        fields = [
            "id", "report_type", "report_type_label", "label", "format",
            "period_days", "file_size", "created_at", "requested_by_name",
        ]
        read_only_fields = fields
