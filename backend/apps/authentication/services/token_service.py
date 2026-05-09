"""
Service de gestion des tokens JWT et OAuth2.
Refresh token, révocation, vérification d'expiration.
"""
import logging
from datetime import timedelta

import django.utils.timezone as timezone
import httpx
from django.conf import settings

from utils.encryption import decrypt_value, encrypt_value

logger = logging.getLogger(__name__)


class TokenService:
    """
    Service de gestion des tokens OAuth2 pour les connecteurs.
    Gère le refresh automatique avant chaque appel API.
    """

    REFRESH_THRESHOLD_SECONDS = 300  # Rafraîchir si < 5 minutes restantes

    def is_token_expiring_soon(self, connector) -> bool:
        """
        Vérifie si le token OAuth2 d'un connecteur va expirer dans moins de 5 minutes.
        """
        if not connector.token_expires_at:
            return True
        remaining = connector.token_expires_at - timezone.now()
        return remaining.total_seconds() < self.REFRESH_THRESHOLD_SECONDS

    def get_valid_access_token(self, connector) -> str:
        """
        Retourne un access token valide pour le connecteur.
        Si le token expire bientôt, le rafraîchit automatiquement.
        """
        if self.is_token_expiring_soon(connector):
            logger.info(
                "Token OAuth2 expirant bientôt pour %s. Rafraîchissement...",
                connector.name,
            )
            self.refresh_token(connector)

        if connector.oauth_access_token:
            return decrypt_value(connector.oauth_access_token)
        raise ValueError(f"Aucun access token disponible pour le connecteur {connector.name}.")

    def refresh_token(self, connector) -> None:
        """
        Rafraîchit le token OAuth2 d'un connecteur via le token endpoint.
        Met à jour les tokens chiffrés dans la base de données.
        """
        if not connector.oauth_refresh_token:
            raise ValueError(
                f"Aucun refresh token disponible pour {connector.name}. "
                "Réauthentifiez le connecteur via OAuth2."
            )

        refresh_token = decrypt_value(connector.oauth_refresh_token)

        if connector.source_type == "microsoft365":
            token_data = self._refresh_microsoft(refresh_token)
        elif connector.source_type == "google_workspace":
            token_data = self._refresh_google(refresh_token)
        else:
            raise ValueError(f"Type de connecteur non supporté pour le refresh : {connector.source_type}")

        connector.oauth_access_token = encrypt_value(token_data["access_token"])
        if token_data.get("refresh_token"):
            connector.oauth_refresh_token = encrypt_value(token_data["refresh_token"])
        expires_in = token_data.get("expires_in", 3600)
        connector.token_expires_at = timezone.now() + timedelta(seconds=int(expires_in))
        connector.save(update_fields=["oauth_access_token", "oauth_refresh_token", "token_expires_at"])
        logger.info("Token OAuth2 rafraîchi avec succès pour %s.", connector.name)

    def _refresh_microsoft(self, refresh_token: str) -> dict:
        """Rafraîchit le token Microsoft via Azure AD."""
        tenant_id = settings.MICROSOFT_TENANT_ID or "common"
        token_url = f"https://login.microsoftonline.com/{tenant_id}/oauth2/v2.0/token"
        payload = {
            "grant_type": "refresh_token",
            "refresh_token": refresh_token,
            "client_id": settings.MICROSOFT_CLIENT_ID,
            "client_secret": settings.MICROSOFT_CLIENT_SECRET,
            "scope": " ".join(settings.MICROSOFT_SCOPES),
        }
        return self._post_token(token_url, payload, "Microsoft")

    def _refresh_google(self, refresh_token: str) -> dict:
        """Rafraîchit le token Google."""
        token_url = "https://oauth2.googleapis.com/token"
        payload = {
            "grant_type": "refresh_token",
            "refresh_token": refresh_token,
            "client_id": settings.GOOGLE_CLIENT_ID,
            "client_secret": settings.GOOGLE_CLIENT_SECRET,
        }
        return self._post_token(token_url, payload, "Google")

    @staticmethod
    def _post_token(url: str, payload: dict, provider: str) -> dict:
        """Effectue la requête POST vers le token endpoint."""
        with httpx.Client(timeout=30) as client:
            response = client.post(url, data=payload)
        if response.status_code != 200:
            logger.error(
                "Refresh token %s échoué : %d %s",
                provider,
                response.status_code,
                response.text,
            )
            raise ValueError(
                f"Refresh token {provider} échoué : "
                f"{response.json().get('error_description', response.text)}"
            )
        return response.json()


token_service = TokenService()
