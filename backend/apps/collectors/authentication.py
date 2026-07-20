"""
Authentification DRF par token d'agent bearer — RÉSERVÉE à l'endpoint
d'ingestion HTTP (/api/ingest/agent/logs/). Ne JAMAIS ajouter cette classe à
REST_FRAMEWORK["DEFAULT_AUTHENTICATION_CLASSES"] : un token d'agent ne doit
jamais pouvoir authentifier une requête vers un endpoint utilisateur normal.
"""
import hashlib

from django.utils import timezone
from rest_framework.authentication import BaseAuthentication, get_authorization_header
from rest_framework.exceptions import AuthenticationFailed

from .models import AgentEnrollmentToken

TOKEN_PREFIX = "logplus_agt_"


class AgentTokenPrincipal:
    """
    Objet "utilisateur" factice pour request.user quand l'authentification
    passe par un token d'agent — jamais un vrai User (pas de session
    humaine). Porte l'organisation et le connecteur résolus depuis le token.
    """

    is_authenticated = True
    is_anonymous = False
    is_superuser = False

    def __init__(self, token: AgentEnrollmentToken):
        self.token = token
        self.pk = token.id  # requis par ScopedRateThrottle (throttling par identité authentifiée)
        self.id = token.id
        self.organization_id = token.organization_id
        self.organization = token.organization
        self.connector = token.connector


class AgentTokenAuthentication(BaseAuthentication):
    keyword = "Bearer"

    def authenticate(self, request):
        auth = get_authorization_header(request).decode("utf-8", errors="ignore")
        if not auth.startswith(f"{self.keyword} {TOKEN_PREFIX}"):
            return None  # laisse la chance à un autre authenticator (aucun ici, volontairement)

        raw = auth[len(self.keyword) + 1:][len(TOKEN_PREFIX):]
        if len(raw) < 8:
            raise AuthenticationFailed("Token d'agent invalide.")

        prefix = raw[:8]
        token_hash = hashlib.sha256(raw.encode()).hexdigest()

        try:
            token = AgentEnrollmentToken.objects.select_related("organization", "connector").get(
                token_prefix=prefix, token_hash=token_hash, is_active=True,
            )
        except AgentEnrollmentToken.DoesNotExist:
            raise AuthenticationFailed("Token d'agent invalide.")

        if token.expires_at and token.expires_at < timezone.now():
            raise AuthenticationFailed("Token d'agent expiré.")

        x_forwarded = request.META.get("HTTP_X_FORWARDED_FOR")
        client_ip = x_forwarded.split(",")[0].strip() if x_forwarded else request.META.get("REMOTE_ADDR")

        token.last_used_at = timezone.now()
        token.last_used_ip = client_ip
        token.save(update_fields=["last_used_at", "last_used_ip"])

        return (AgentTokenPrincipal(token), token)
