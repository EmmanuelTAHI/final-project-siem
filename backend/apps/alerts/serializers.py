"""
Serializers pour les alertes et commentaires.
"""
from rest_framework import serializers

from apps.logs.serializers import NormalizedLogBriefSerializer

from .models import Alert, AlertComment


class AlertCommentSerializer(serializers.ModelSerializer):
    author_email = serializers.CharField(source="author.email", read_only=True, allow_null=True)
    author_full_name = serializers.CharField(
        source="author.full_name", read_only=True, allow_null=True
    )

    class Meta:
        model = AlertComment
        fields = [
            "id",
            "alert",
            "author",
            "author_email",
            "author_full_name",
            "content",
            "created_at",
        ]
        read_only_fields = ["id", "alert", "author", "author_email", "author_full_name", "created_at"]


class AlertCommentCreateSerializer(serializers.ModelSerializer):
    class Meta:
        model = AlertComment
        fields = ["content"]

    def validate_content(self, value):
        if not value.strip():
            raise serializers.ValidationError("Le commentaire ne peut pas être vide.")
        return value.strip()


class _FlatLogFieldsMixin:
    """
    Champs à plat (event_count / source_ip / user_email) dérivés des logs
    sources. Utilise `source_logs` déjà préchargé par le viewset (pas de N+1).
    Partagé par le serializer complet ET le serializer de liste pour que la
    liste et le détail exposent EXACTEMENT les mêmes champs — sinon le panneau
    de détail (qui lit la ligne de liste) affiche des champs vides.
    """

    def _first_log(self, obj):
        logs = list(obj.source_logs.all())
        return logs[0] if logs else None

    def get_event_count(self, obj):
        return len(list(obj.source_logs.all()))

    def get_source_ip(self, obj):
        log = self._first_log(obj)
        return getattr(log, "source_ip", None) if log else None

    def get_user_email(self, obj):
        log = self._first_log(obj)
        return getattr(log, "user_email", None) if log else None

    def get_comments_count(self, obj):
        return obj.comments.count()


class AlertSerializer(_FlatLogFieldsMixin, serializers.ModelSerializer):
    """Serializer complet pour la lecture d'une alerte."""

    assigned_to_email = serializers.CharField(
        source="assigned_to.email", read_only=True, allow_null=True
    )
    rule_name = serializers.CharField(source="rule.name", read_only=True, allow_null=True)
    rule_mitre_tactic = serializers.CharField(
        source="rule.mitre_tactic", read_only=True, allow_null=True
    )
    rule_mitre_technique = serializers.CharField(
        source="rule.mitre_technique", read_only=True, allow_null=True
    )
    comments_count = serializers.SerializerMethodField()
    comments = AlertCommentSerializer(many=True, read_only=True)
    event_count = serializers.SerializerMethodField()
    source_ip = serializers.SerializerMethodField()
    user_email = serializers.SerializerMethodField()
    time_to_resolve_hours = serializers.ReadOnlyField()
    source_logs_brief = NormalizedLogBriefSerializer(
        source="source_logs", many=True, read_only=True
    )

    class Meta:
        model = Alert
        fields = [
            "id",
            "title",
            "description",
            "severity",
            "status",
            "rule",
            "rule_name",
            "rule_mitre_tactic",
            "rule_mitre_technique",
            "assigned_to",
            "assigned_to_email",
            "event_count",
            "source_ip",
            "user_email",
            "source_logs_brief",
            "created_at",
            "updated_at",
            "resolved_at",
            "resolution_note",
            "time_to_resolve_hours",
            "comments_count",
            "comments",
            "ai_summary",
            "ai_recommended_actions",
            "ai_summary_generated_at",
        ]
        read_only_fields = ["id", "created_at", "updated_at"]


class AlertBriefSerializer(_FlatLogFieldsMixin, serializers.ModelSerializer):
    """
    Serializer de liste. Enrichi avec description + champs à plat pour que le
    panneau de détail (qui lit la ligne de liste) ait tout ce qu'il faut sans
    perdre les données au refetch. Les commentaires complets restent réservés
    au serializer de détail (chargés à l'ouverture).
    """

    rule_name = serializers.CharField(source="rule.name", read_only=True, allow_null=True)
    rule_mitre_tactic = serializers.CharField(
        source="rule.mitre_tactic", read_only=True, allow_null=True
    )
    rule_mitre_technique = serializers.CharField(
        source="rule.mitre_technique", read_only=True, allow_null=True
    )
    assigned_to_email = serializers.CharField(
        source="assigned_to.email", read_only=True, allow_null=True
    )
    event_count = serializers.SerializerMethodField()
    source_ip = serializers.SerializerMethodField()
    user_email = serializers.SerializerMethodField()
    comments_count = serializers.SerializerMethodField()

    class Meta:
        model = Alert
        fields = [
            "id",
            "title",
            "description",
            "severity",
            "status",
            "rule",
            "rule_name",
            "rule_mitre_tactic",
            "rule_mitre_technique",
            "assigned_to_email",
            "event_count",
            "source_ip",
            "user_email",
            "comments_count",
            "resolution_note",
            "created_at",
            "updated_at",
        ]


class AlertUpdateSerializer(serializers.ModelSerializer):
    """Serializer pour la mise à jour partielle d'une alerte."""

    class Meta:
        model = Alert
        fields = ["status", "assigned_to", "resolution_note"]

    def validate_status(self, value):
        valid_statuses = [c[0] for c in Alert.STATUS_CHOICES]
        if value not in valid_statuses:
            raise serializers.ValidationError(
                f"Statut invalide. Valeurs acceptées : {', '.join(valid_statuses)}"
            )
        return value

    def update(self, instance, validated_data):
        from django.utils import timezone
        if validated_data.get("status") in ("resolved", "false_positive"):
            if not instance.resolved_at:
                validated_data["resolved_at"] = timezone.now()
        return super().update(instance, validated_data)
