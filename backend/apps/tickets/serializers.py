"""
Serializers pour les tickets, commentaires et activité.
"""
from rest_framework import serializers

from apps.users.models import User

from .models import Ticket, TicketActivity, TicketComment


class TicketUserBriefSerializer(serializers.ModelSerializer):
    full_name = serializers.ReadOnlyField()

    class Meta:
        model = User
        fields = ["id", "email", "full_name"]


class TicketCommentSerializer(serializers.ModelSerializer):
    author_email = serializers.CharField(source="author.email", read_only=True, allow_null=True)
    author_full_name = serializers.CharField(source="author.full_name", read_only=True, allow_null=True)

    class Meta:
        model = TicketComment
        fields = ["id", "ticket", "author", "author_email", "author_full_name", "content", "created_at"]
        read_only_fields = ["id", "ticket", "author", "author_email", "author_full_name", "created_at"]


class TicketCommentCreateSerializer(serializers.ModelSerializer):
    class Meta:
        model = TicketComment
        fields = ["content"]

    def validate_content(self, value):
        if not value.strip():
            raise serializers.ValidationError("Le commentaire ne peut pas être vide.")
        return value.strip()


class TicketActivitySerializer(serializers.ModelSerializer):
    actor_email = serializers.CharField(source="actor.email", read_only=True, allow_null=True)
    actor_full_name = serializers.CharField(source="actor.full_name", read_only=True, allow_null=True)
    action_display = serializers.CharField(source="get_action_display", read_only=True)

    class Meta:
        model = TicketActivity
        fields = [
            "id", "ticket", "actor", "actor_email", "actor_full_name",
            "action", "action_display", "from_value", "to_value", "created_at",
        ]
        read_only_fields = fields


class _TicketFlatFieldsMixin:
    """Champs à plat partagés par le serializer de liste ET de détail, pour
    que le panneau de détail (qui lit d'abord la ligne de liste) affiche
    immédiatement les mêmes informations sans attendre un second appel."""

    def get_comments_count(self, obj):
        return obj.comments.count()


class TicketSerializer(_TicketFlatFieldsMixin, serializers.ModelSerializer):
    """Serializer complet — détail d'un ticket."""

    display_id = serializers.ReadOnlyField()
    is_overdue = serializers.ReadOnlyField()
    reporter = TicketUserBriefSerializer(read_only=True)
    assignee = TicketUserBriefSerializer(read_only=True)
    alert_title = serializers.CharField(source="alert.title", read_only=True, allow_null=True)
    alert_severity = serializers.CharField(source="alert.severity", read_only=True, allow_null=True)
    comments_count = serializers.SerializerMethodField()
    comments = TicketCommentSerializer(many=True, read_only=True)
    activities = TicketActivitySerializer(many=True, read_only=True)

    class Meta:
        model = Ticket
        fields = [
            "id", "display_id", "number", "title", "description",
            "status", "priority",
            "alert", "alert_title", "alert_severity",
            "reporter", "assignee",
            "due_date", "is_overdue", "resolution_note",
            "created_at", "updated_at", "resolved_at", "closed_at",
            "comments_count", "comments", "activities",
        ]
        read_only_fields = ["id", "display_id", "number", "created_at", "updated_at", "resolved_at", "closed_at"]


class TicketListSerializer(_TicketFlatFieldsMixin, serializers.ModelSerializer):
    """Serializer de liste — plus léger (pas de commentaires/activités complets)."""

    display_id = serializers.ReadOnlyField()
    is_overdue = serializers.ReadOnlyField()
    reporter_email = serializers.CharField(source="reporter.email", read_only=True, allow_null=True)
    assignee_email = serializers.CharField(source="assignee.email", read_only=True, allow_null=True)
    assignee_full_name = serializers.CharField(source="assignee.full_name", read_only=True, allow_null=True)
    alert_title = serializers.CharField(source="alert.title", read_only=True, allow_null=True)
    alert_severity = serializers.CharField(source="alert.severity", read_only=True, allow_null=True)
    comments_count = serializers.SerializerMethodField()

    class Meta:
        model = Ticket
        fields = [
            "id", "display_id", "number", "title", "description",
            "status", "priority",
            "alert", "alert_title", "alert_severity",
            "reporter_email", "assignee", "assignee_email", "assignee_full_name",
            "due_date", "is_overdue",
            "created_at", "updated_at", "resolved_at", "closed_at",
            "comments_count",
        ]


class TicketCreateSerializer(serializers.ModelSerializer):
    """Création — depuis une alerte (champ `alert`) ou en libre (sans alerte)."""

    class Meta:
        model = Ticket
        fields = ["title", "description", "priority", "status", "alert", "assignee", "due_date"]
        extra_kwargs = {
            "description": {"required": False, "allow_blank": True},
            "status": {"required": False},
            "priority": {"required": False},
        }

    def validate_title(self, value):
        if not value.strip():
            raise serializers.ValidationError("Le titre est requis.")
        return value.strip()

    def validate_alert(self, value):
        if value is None:
            return value
        request = self.context.get("request")
        if request and value.organization_id != request.user.organization_id:
            raise serializers.ValidationError("Cette alerte n'appartient pas à votre organisation.")
        return value

    def validate_assignee(self, value):
        if value is None:
            return value
        request = self.context.get("request")
        if request and value.organization_id != request.user.organization_id:
            raise serializers.ValidationError("Cet utilisateur n'appartient pas à votre organisation.")
        return value


class TicketUpdateSerializer(serializers.ModelSerializer):
    """Mise à jour partielle — statut, priorité, assignation, échéance, résolution."""

    class Meta:
        model = Ticket
        fields = ["title", "description", "status", "priority", "assignee", "due_date", "resolution_note"]
        extra_kwargs = {"title": {"required": False}}

    def validate_status(self, value):
        valid = [c[0] for c in Ticket.STATUS_CHOICES]
        if value not in valid:
            raise serializers.ValidationError(f"Statut invalide. Valeurs acceptées : {', '.join(valid)}")
        return value

    def validate_assignee(self, value):
        if value is None:
            return value
        request = self.context.get("request")
        if request and value.organization_id != request.user.organization_id:
            raise serializers.ValidationError("Cet utilisateur n'appartient pas à votre organisation.")
        return value
