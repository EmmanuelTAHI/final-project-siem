from rest_framework import serializers
from .models import ThreatIndicator, EnrichedLog


class ThreatIndicatorSerializer(serializers.ModelSerializer):
    class Meta:
        model = ThreatIndicator
        fields = [
            "id", "indicator_type", "value", "reputation_score", "confidence",
            "source", "tags", "is_malicious", "last_seen", "first_seen", "raw_data",
        ]
        read_only_fields = ["id", "first_seen"]


class EnrichedLogSerializer(serializers.ModelSerializer):
    indicators = ThreatIndicatorSerializer(many=True, read_only=True)
    log_id = serializers.UUIDField(source="log.id", read_only=True)
    source_ip = serializers.CharField(source="log.source_ip", read_only=True)
    user_email = serializers.CharField(source="log.user_email", read_only=True)

    class Meta:
        model = EnrichedLog
        fields = ["id", "log_id", "source_ip", "user_email", "indicators", "max_score", "is_threat", "enriched_at"]
