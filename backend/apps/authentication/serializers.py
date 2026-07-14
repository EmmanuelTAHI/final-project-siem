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
        token["is_superuser"] = user.is_superuser
        token["organization_id"] = str(user.organization_id) if user.organization_id else None
        token["organization_name"] = user.organization.name if user.organization_id else None
        return token

    def validate(self, attrs):
        data = super().validate(attrs)
        data["user"] = {
            "id": str(self.user.id),
            "email": self.user.email,
            "full_name": self.user.full_name,
            "role": self.user.role,
            "is_superuser": self.user.is_superuser,
            "organization_id": str(self.user.organization_id) if self.user.organization_id else None,
            "organization_name": self.user.organization.name if self.user.organization_id else None,
        }
        return data


class LoginSerializer(serializers.Serializer):
    """Serializer pour la connexion par email/mot de passe."""

    email = serializers.EmailField(required=True)
    password = serializers.CharField(required=True, write_only=True, style={"input_type": "password"})


class LogoutSerializer(serializers.Serializer):
    """Serializer pour la déconnexion — blackliste le refresh token."""

    refresh = serializers.CharField(required=True)


class PasswordResetRequestSerializer(serializers.Serializer):
    """Serializer pour la demande de réinitialisation de mot de passe."""

    email = serializers.EmailField(required=True)


class PasswordResetConfirmSerializer(serializers.Serializer):
    """Serializer pour la confirmation de réinitialisation de mot de passe."""

    token = serializers.CharField(required=True)
    password = serializers.CharField(required=True, write_only=True, style={"input_type": "password"})


class TokenRefreshSerializer(serializers.Serializer):
    """Serializer pour le renouvellement du token d'accès."""

    refresh = serializers.CharField(required=True)


class RegisterSerializer(serializers.Serializer):
    """
    Inscription publique : crée une nouvelle Organization + son premier
    utilisateur (admin, inactif jusqu'à vérification email).
    """

    email = serializers.EmailField(required=True)
    password = serializers.CharField(required=True, write_only=True, style={"input_type": "password"})
    first_name = serializers.CharField(required=True, max_length=150)
    last_name = serializers.CharField(required=True, max_length=150)
    organization_name = serializers.CharField(required=True, max_length=200)

    def validate_email(self, value):
        value = value.strip().lower()
        if User.objects.filter(email__iexact=value).exists():
            # Pas de distinction de message ici — la vue renvoie un succès
            # générique dans tous les cas pour éviter l'énumération de comptes.
            pass
        return value

    def validate_password(self, value):
        from django.contrib.auth.password_validation import validate_password
        validate_password(value)
        return value


class VerifyEmailSerializer(serializers.Serializer):
    token = serializers.CharField(required=True)


class InviteUserSerializer(serializers.Serializer):
    """Invitation d'un membre par un admin d'organisation (déjà authentifié)."""

    email = serializers.EmailField(required=True)
    first_name = serializers.CharField(required=True, max_length=150)
    last_name = serializers.CharField(required=True, max_length=150)
    role = serializers.ChoiceField(choices=User.ROLE_CHOICES, default="viewer")

    def validate_email(self, value):
        value = value.strip().lower()
        if User.objects.filter(email__iexact=value).exists():
            raise serializers.ValidationError("Un utilisateur avec cet email existe déjà.")
        return value


class AcceptInviteSerializer(serializers.Serializer):
    token = serializers.CharField(required=True)
    password = serializers.CharField(required=True, write_only=True, style={"input_type": "password"})

    def validate_password(self, value):
        from django.contrib.auth.password_validation import validate_password
        validate_password(value)
        return value


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
