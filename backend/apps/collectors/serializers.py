"""
Serializers pour les connecteurs et jobs de collecte.
"""
from rest_framework import serializers

from .models import CollectionJob, ConnectorConfig


class ConnectorConfigSerializer(serializers.ModelSerializer):
    """Serializer en lecture pour les connecteurs — champs compatibles avec le type Connector frontend."""

    source_type_display = serializers.CharField(source="get_source_type_display", read_only=True)
    created_by_email = serializers.CharField(source="created_by.email", read_only=True, allow_null=True)

    # Alias pour compatibilité frontend
    connector_type = serializers.CharField(source="source_type", read_only=True)
    display_name = serializers.CharField(source="name", read_only=True)
    description = serializers.SerializerMethodField()
    status = serializers.SerializerMethodField()
    logs_collected = serializers.SerializerMethodField()
    logs_collected_24h = serializers.SerializerMethodField()
    last_job_status = serializers.SerializerMethodField()
    last_job_at = serializers.SerializerMethodField()

    class Meta:
        model = ConnectorConfig
        fields = [
            "id", "name", "source_type", "source_type_display",
            "connector_type", "display_name", "description",
            "status", "is_active",
            "logs_collected", "logs_collected_24h",
            "last_job_status", "last_job_at",
            "polling_interval_seconds", "last_collected_at",
            "token_expires_at", "created_by", "created_by_email", "created_at",
        ]
        read_only_fields = ["id", "created_at", "last_collected_at"]

    def get_description(self, obj):
        labels = {
            "microsoft365": "Collecte des logs Microsoft 365 via MS Graph API",
            "google_workspace": "Collecte des logs Google Workspace via Admin SDK",
            "wazuh": "Intégration Wazuh SIEM (agents + serveur)",
            "syslog": "Réception syslog UDP/TCP",
        }
        return labels.get(obj.source_type, obj.source_type)

    def get_status(self, obj):
        if not obj.is_active:
            return "inactive"
        last_job = obj.jobs.order_by("-started_at").first()
        if last_job is None:
            return "active"
        return "error" if last_job.status == "failed" else "active"

    def _last_job(self, obj):
        return obj.jobs.order_by("-started_at").first()

    def get_logs_collected(self, obj):
        from django.db.models import Sum
        total = obj.jobs.filter(status="success").aggregate(t=Sum("logs_collected_count"))["t"]
        return total or 0

    def get_logs_collected_24h(self, obj):
        from django.utils import timezone
        from datetime import timedelta
        from django.db.models import Sum
        since = timezone.now() - timedelta(hours=24)
        total = obj.jobs.filter(status="success", started_at__gte=since).aggregate(t=Sum("logs_collected_count"))["t"]
        return total or 0

    def get_last_job_status(self, obj):
        j = self._last_job(obj)
        return j.status if j else None

    def get_last_job_at(self, obj):
        j = self._last_job(obj)
        return j.started_at.isoformat() if (j and j.started_at) else None


class ConnectorConfigCreateSerializer(serializers.ModelSerializer):
    """Serializer pour créer un connecteur avec credentials en clair (chiffrés à la sauvegarde)."""

    credentials = serializers.DictField(
        write_only=True,
        required=False,
        help_text="Credentials en clair : client_id, client_secret, tenant_id, scopes",
    )

    class Meta:
        model = ConnectorConfig
        fields = [
            "name",
            "source_type",
            "credentials",
            "polling_interval_seconds",
            "is_active",
        ]

    def create(self, validated_data):
        credentials = validated_data.pop("credentials", {})
        connector = ConnectorConfig(**validated_data)
        if credentials:
            connector.set_credentials(credentials)
        connector.save()
        return connector

    def update(self, instance, validated_data):
        credentials = validated_data.pop("credentials", None)
        if credentials is not None:
            instance.set_credentials(credentials)
        for attr, value in validated_data.items():
            setattr(instance, attr, value)
        instance.save()
        return instance


class CollectionJobSerializer(serializers.ModelSerializer):
    """Serializer pour l'historique des jobs de collecte — compatible type CollectorJob frontend."""

    connector_name = serializers.CharField(source="connector.name", read_only=True)
    connector_type = serializers.CharField(source="connector.source_type", read_only=True)
    duration_seconds = serializers.ReadOnlyField()
    # Alias frontend
    logs_collected = serializers.IntegerField(source="logs_collected_count", read_only=True)
    completed_at = serializers.DateTimeField(source="finished_at", read_only=True)

    class Meta:
        model = CollectionJob
        fields = [
            "id", "connector", "connector_name", "connector_type",
            "status", "logs_collected_count", "logs_collected",
            "error_message", "started_at", "finished_at", "completed_at",
            "duration_seconds",
        ]
        read_only_fields = fields
