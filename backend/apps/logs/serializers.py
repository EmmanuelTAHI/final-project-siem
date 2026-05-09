"""
Serializers pour les logs bruts et normalisés.
"""
from rest_framework import serializers

from .models import NormalizedLog, RawLog


class RawLogSerializer(serializers.ModelSerializer):
    connector_name = serializers.CharField(source="connector.name", read_only=True, allow_null=True)

    class Meta:
        model = RawLog
        fields = [
            "id",
            "source_type",
            "connector",
            "connector_name",
            "raw_data",
            "received_at",
            "is_normalized",
        ]
        read_only_fields = fields


class NormalizedLogSerializer(serializers.ModelSerializer):
    class Meta:
        model = NormalizedLog
        fields = [
            "id",
            "raw_log",
            "event_time",
            "source_ip",
            "destination_ip",
            "user_email",
            "user_id",
            "action",
            "outcome",
            "resource",
            "geo_country",
            "geo_city",
            "geo_latitude",
            "geo_longitude",
            "user_agent",
            "severity",
            "source_type",
            "extra_fields",
            "indexed_at",
        ]
        read_only_fields = fields


class NormalizedLogBriefSerializer(serializers.ModelSerializer):
    """Serializer compact pour les listes et les références."""

    class Meta:
        model = NormalizedLog
        fields = [
            "id",
            "event_time",
            "source_type",
            "action",
            "outcome",
            "severity",
            "user_email",
            "source_ip",
            "geo_country",
        ]
