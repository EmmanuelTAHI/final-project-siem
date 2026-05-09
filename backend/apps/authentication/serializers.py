"""
Serializers pour l'authentification JWT et OAuth2.
"""
from rest_framework import serializers
from rest_framework_simplejwt.serializers import TokenObtainPairSerializer

from apps.users.models import User


class CustomTokenObtainPairSerializer(TokenObtainPairSerializer):
    """
    Serializer JWT personnalisé qui ajoute les informations utilisateur
    dans le payload du token et dans la réponse.
    """

    username_field = "email"

    @classmethod
    def get_token(cls, user):
        token = super().get_token(user)
        token["email"] = user.email
        token["role"] = user.role
        token["full_name"] = user.full_name
        return token

    def validate(self, attrs):
        data = super().validate(attrs)
        data["user"] = {
            "id": str(self.user.id),
            "email": self.user.email,
            "full_name": self.user.full_name,
            "role": self.user.role,
        }
        return data


class LoginSerializer(serializers.Serializer):
    """Serializer pour la connexion par email/mot de passe."""

    email = serializers.EmailField(required=True)
    password = serializers.CharField(required=True, write_only=True, style={"input_type": "password"})


class LogoutSerializer(serializers.Serializer):
    """Serializer pour la déconnexion — blackliste le refresh token."""

    refresh = serializers.CharField(required=True)


class TokenRefreshSerializer(serializers.Serializer):
    """Serializer pour le renouvellement du token d'accès."""

    refresh = serializers.CharField(required=True)


class OAuthCallbackSerializer(serializers.Serializer):
    """Serializer pour les callbacks OAuth2."""

    code = serializers.CharField(required=True)
    state = serializers.CharField(required=True)


class LinkedAccountSerializer(serializers.ModelSerializer):
    """Vue publique d'un LinkedAccount (sans tokens)."""

    class Meta:
        from .models import LinkedAccount

        model = LinkedAccount
        fields = [
            "id", "provider", "provider_user_id", "provider_email",
            "provider_display_name", "avatar_url", "scopes",
            "status", "last_polled_at", "linked_at",
        ]
        read_only_fields = fields


class SecurityNotificationSerializer(serializers.ModelSerializer):
    """Vue publique d'une SecurityNotification (avec un token de confirmation court si pending)."""

    confirmation_token = serializers.SerializerMethodField()
    confirmation_status = serializers.SerializerMethodField()

    class Meta:
        from .models import SecurityNotification

        model = SecurityNotification
        fields = [
            "id", "kind", "level", "title", "body",
            "metadata", "is_read", "created_at", "read_at",
            "confirmation_token", "confirmation_status",
        ]
        read_only_fields = fields

    def get_confirmation_token(self, obj):
        if not obj.confirmation_id or obj.confirmation.status != "pending":
            return None
        from .services.notification_service import make_confirmation_token

        return make_confirmation_token(obj.confirmation.id)

    def get_confirmation_status(self, obj):
        return obj.confirmation.status if obj.confirmation_id else None


class ProviderLoginEventSerializer(serializers.ModelSerializer):
    class Meta:
        from .models import ProviderLoginEvent

        model = ProviderLoginEvent
        fields = [
            "id", "event_type", "occurred_at",
            "ip_address", "browser", "os", "device_type",
            "geo_country", "geo_city",
            "is_known_device", "is_known_location", "risk_score",
        ]
        read_only_fields = fields
