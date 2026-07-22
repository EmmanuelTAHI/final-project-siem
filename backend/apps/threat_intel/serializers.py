from rest_framework import serializers
from .models import Asset, AssetVulnerability, CVERecord, EnrichedLog, ThreatIndicator


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


class CVERecordSerializer(serializers.ModelSerializer):
    class Meta:
        model = CVERecord
        fields = [
            "id", "cve_id", "description", "cvss_score", "severity",
            "vendor_project", "product", "published_date", "modified_date",
            "is_kev", "kev_date_added", "kev_due_date", "kev_ransomware_use",
            "kev_required_action",
        ]
        read_only_fields = fields


class AssetVulnerabilitySerializer(serializers.ModelSerializer):
    cve_id = serializers.CharField(source="cve.cve_id", read_only=True)
    cve_cvss_score = serializers.FloatField(source="cve.cvss_score", read_only=True)
    cve_is_kev = serializers.BooleanField(source="cve.is_kev", read_only=True)
    cve_description = serializers.CharField(source="cve.description", read_only=True)
    asset_name = serializers.CharField(source="asset.name", read_only=True)

    class Meta:
        model = AssetVulnerability
        fields = [
            "id", "asset", "asset_name", "cve", "cve_id", "cve_cvss_score",
            "cve_is_kev", "cve_description", "status", "matched_reason", "matched_at",
        ]
        read_only_fields = ["id", "asset", "cve", "matched_reason", "matched_at"]


class AssetSerializer(serializers.ModelSerializer):
    open_vulnerabilities_count = serializers.SerializerMethodField()
    kev_vulnerabilities_count = serializers.SerializerMethodField()

    class Meta:
        model = Asset
        fields = [
            "id", "name", "asset_type", "vendor", "product", "version",
            "hostname", "ip_address", "criticality", "source", "last_seen",
            "created_at", "updated_at", "open_vulnerabilities_count", "kev_vulnerabilities_count",
        ]
        read_only_fields = ["id", "created_at", "updated_at", "source"]

    def get_open_vulnerabilities_count(self, obj):
        return obj.vulnerabilities.filter(status="open").count()

    def get_kev_vulnerabilities_count(self, obj):
        return obj.vulnerabilities.filter(status="open", cve__is_kev=True).count()
