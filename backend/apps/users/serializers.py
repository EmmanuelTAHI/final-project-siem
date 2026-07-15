"""
Serializers pour les utilisateurs et l'audit trail.
"""
from django.contrib.auth.password_validation import validate_password
from rest_framework import serializers

from .models import AuditTrail, User


class UserSerializer(serializers.ModelSerializer):
    """Serializer complet pour la lecture d'un utilisateur."""

    full_name = serializers.ReadOnlyField()

    class Meta:
        model = User
        fields = [
            "id",
            "email",
            "first_name",
            "last_name",
            "full_name",
            "role",
            "is_active",
            "date_joined",
            "last_login",
            "created_at",
            "updated_at",
            "email_notifications",
            "critical_alert_emails",
            "weekly_report_email",
        ]
        read_only_fields = ["id", "date_joined", "last_login", "created_at", "updated_at"]


class SelfProfileUpdateSerializer(serializers.ModelSerializer):
    """
    Serializer pour la mise à jour de son PROPRE profil (GET/PATCH /api/users/me/).
    N'expose jamais `role`/`is_active` : un utilisateur ne doit jamais pouvoir
    s'auto-promouvoir admin ou se réactiver via ce endpoint (contrairement à
    UserUpdateSerializer, réservé à la gestion admin d'autres utilisateurs).
    """

    class Meta:
        model = User
        fields = [
            "first_name", "last_name", "email",
            "email_notifications", "critical_alert_emails", "weekly_report_email",
        ]


class UserCreateSerializer(serializers.ModelSerializer):
    """Serializer pour la création d'un utilisateur."""

    password = serializers.CharField(
        write_only=True,
        required=True,
        validators=[validate_password],
        style={"input_type": "password"},
    )
    password_confirm = serializers.CharField(
        write_only=True,
        required=True,
        style={"input_type": "password"},
    )

    class Meta:
        model = User
        fields = [
            "email",
            "first_name",
            "last_name",
            "role",
            "password",
            "password_confirm",
        ]

    def validate(self, attrs):
        if attrs["password"] != attrs.pop("password_confirm"):
            raise serializers.ValidationError(
                {"password_confirm": "Les mots de passe ne correspondent pas."}
            )
        return attrs

    def create(self, validated_data):
        # organization vient toujours de request.user (jamais du payload
        # client) — passé explicitement par la vue via serializer.save(...).
        user = User.objects.create_user(
            email=validated_data["email"],
            password=validated_data["password"],
            first_name=validated_data["first_name"],
            last_name=validated_data["last_name"],
            role=validated_data.get("role", "viewer"),
            organization=validated_data.get("organization"),
        )
        return user


class UserUpdateSerializer(serializers.ModelSerializer):
    """Serializer pour la mise à jour d'un utilisateur (sans password)."""

    class Meta:
        model = User
        fields = ["first_name", "last_name", "role", "is_active"]


class ChangePasswordSerializer(serializers.Serializer):
    """Serializer pour le changement de mot de passe."""

    old_password = serializers.CharField(
        required=True,
        write_only=True,
        style={"input_type": "password"},
    )
    new_password = serializers.CharField(
        required=True,
        write_only=True,
        validators=[validate_password],
        style={"input_type": "password"},
    )
    new_password_confirm = serializers.CharField(
        required=True,
        write_only=True,
        style={"input_type": "password"},
    )

    def validate(self, attrs):
        if attrs["new_password"] != attrs["new_password_confirm"]:
            raise serializers.ValidationError(
                {"new_password_confirm": "Les nouveaux mots de passe ne correspondent pas."}
            )
        return attrs

    def validate_old_password(self, value):
        user = self.context["request"].user
        if not user.check_password(value):
            raise serializers.ValidationError("Mot de passe actuel incorrect.")
        return value


class AuditTrailSerializer(serializers.ModelSerializer):
    """Serializer en lecture seule pour l'audit trail."""

    user_email = serializers.CharField(source="user.email", read_only=True, allow_null=True)
    user_full_name = serializers.CharField(
        source="user.full_name", read_only=True, allow_null=True
    )

    class Meta:
        model = AuditTrail
        fields = [
            "id",
            "user",
            "user_email",
            "user_full_name",
            "action",
            "target_model",
            "target_id",
            "ip_address",
            "user_agent",
            "extra_data",
            "timestamp",
        ]
        read_only_fields = fields
