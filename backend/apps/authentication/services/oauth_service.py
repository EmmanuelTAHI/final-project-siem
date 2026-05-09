"""
Service OAuth2 avec PKCE (RFC 6749 + RFC 7636).
Implémente le flow complet : initiation, callback, refresh.
"""
import base64
import hashlib
import logging
import os
import secrets
from datetime import timedelta
from urllib.parse import urlencode

import django.utils.timezone as timezone
import httpx
from django.conf import settings
from django.core.cache import cache

from utils.encryption import decrypt_value, encrypt_value

logger = logging.getLogger(__name__)

OAUTH_STATE_TTL = 600  # 10 minutes


class OAuthService:
    """
    Service centralisant la logique OAuth2 PKCE.
    Conforme à la RFC 7636 (PKCE) et RFC 6749 (OAuth2).
    """

    # ─── PKCE ─────────────────────────────────────────────────────────────────

    @staticmethod
    def generate_code_verifier() -> str:
        """
        Génère un code_verifier conforme RFC 7636.
        96 octets aléatoires → base64url sans padding → ~128 caractères.
        """
        raw = secrets.token_bytes(96)
        verifier = base64.urlsafe_b64encode(raw).rstrip(b"=").decode("utf-8")
        return verifier

    @staticmethod
    def generate_code_challenge(code_verifier: str) -> str:
        """
        Génère le code_challenge à partir du code_verifier.
        Méthode S256 : SHA256(code_verifier) → base64url sans padding.
        """
        digest = hashlib.sha256(code_verifier.encode("utf-8")).digest()
        challenge = base64.urlsafe_b64encode(digest).rstrip(b"=").decode("utf-8")
        return challenge

    @staticmethod
    def generate_state() -> str:
        """Génère un état aléatoire de 32 octets en hexadécimal."""
        return secrets.token_hex(32)

    # ─── Stockage Redis ────────────────────────────────────────────────────────

    @staticmethod
    def store_state(state: str, code_verifier: str) -> None:
        """Stocke le state et le code_verifier dans Redis avec un TTL de 10 min."""
        key = f"oauth_state:{state}"
        cache.set(key, code_verifier, timeout=OAUTH_STATE_TTL)
        logger.debug("OAuth state stocké dans Redis : %s (TTL=%ds)", key, OAUTH_STATE_TTL)

    @staticmethod
    def retrieve_and_delete_state(state: str) -> str | None:
        """
        Récupère le code_verifier depuis Redis et supprime la clé (usage unique).
        Retourne None si le state est inconnu ou expiré.
        """
        key = f"oauth_state:{state}"
        code_verifier = cache.get(key)
        if code_verifier:
            cache.delete(key)
            logger.debug("OAuth state récupéré et supprimé : %s", key)
        else:
            logger.warning("OAuth state inconnu ou expiré : %s", key)
        return code_verifier

    # ─── Microsoft ────────────────────────────────────────────────────────────

    def initiate_microsoft(self) -> dict:
        """
        Prépare et retourne l'URL d'autorisation Microsoft Azure AD.
        Conforme PKCE RFC 7636.
        """
        code_verifier = self.generate_code_verifier()
        code_challenge = self.generate_code_challenge(code_verifier)
        state = self.generate_state()
        self.store_state(state, code_verifier)

        params = {
            "response_type": "code",
            "client_id": settings.MICROSOFT_CLIENT_ID,
            "redirect_uri": settings.MICROSOFT_REDIRECT_URI,
            "scope": " ".join(settings.MICROSOFT_SCOPES),
            "code_challenge": code_challenge,
            "code_challenge_method": "S256",
            "state": state,
            "response_mode": "query",
        }
        tenant_id = settings.MICROSOFT_TENANT_ID or "common"
        base_url = f"https://login.microsoftonline.com/{tenant_id}/oauth2/v2.0/authorize"
        auth_url = f"{base_url}?{urlencode(params)}"

        return {
            "authorization_url": auth_url,
            "state": state,
        }

    def callback_microsoft(self, code: str, state: str) -> dict:
        """
        Traite le callback Microsoft OAuth2.
        Échange le code contre les tokens et les stocke chiffrés.
        """
        code_verifier = self.retrieve_and_delete_state(state)
        if not code_verifier:
            raise ValueError("State OAuth2 invalide ou expiré. Recommencez le processus.")

        tenant_id = settings.MICROSOFT_TENANT_ID or "common"
        token_url = f"https://login.microsoftonline.com/{tenant_id}/oauth2/v2.0/token"

        payload = {
            "grant_type": "authorization_code",
            "code": code,
            "redirect_uri": settings.MICROSOFT_REDIRECT_URI,
            "client_id": settings.MICROSOFT_CLIENT_ID,
            "client_secret": settings.MICROSOFT_CLIENT_SECRET,
            "code_verifier": code_verifier,
        }

        with httpx.Client(timeout=30) as client:
            response = client.post(token_url, data=payload)

        if response.status_code != 200:
            logger.error(
                "Erreur token Microsoft : %d %s", response.status_code, response.text
            )
            raise ValueError(f"Échange de token Microsoft échoué : {response.json().get('error_description', response.text)}")

        token_data = response.json()
        return self._process_token_response(token_data)

    # ─── Google ───────────────────────────────────────────────────────────────

    def initiate_google(self) -> dict:
        """
        Prépare et retourne l'URL d'autorisation Google OAuth2.
        Conforme PKCE RFC 7636.
        """
        code_verifier = self.generate_code_verifier()
        code_challenge = self.generate_code_challenge(code_verifier)
        state = self.generate_state()
        self.store_state(state, code_verifier)

        params = {
            "response_type": "code",
            "client_id": settings.GOOGLE_CLIENT_ID,
            "redirect_uri": settings.GOOGLE_REDIRECT_URI,
            "scope": " ".join(settings.GOOGLE_SCOPES),
            "code_challenge": code_challenge,
            "code_challenge_method": "S256",
            "state": state,
            "access_type": "offline",
            "prompt": "consent",
        }
        auth_url = f"https://accounts.google.com/o/oauth2/v2/auth?{urlencode(params)}"

        return {
            "authorization_url": auth_url,
            "state": state,
        }

    def callback_google(self, code: str, state: str) -> dict:
        """
        Traite le callback Google OAuth2.
        """
        code_verifier = self.retrieve_and_delete_state(state)
        if not code_verifier:
            raise ValueError("State OAuth2 invalide ou expiré. Recommencez le processus.")

        token_url = "https://oauth2.googleapis.com/token"
        payload = {
            "grant_type": "authorization_code",
            "code": code,
            "redirect_uri": settings.GOOGLE_REDIRECT_URI,
            "client_id": settings.GOOGLE_CLIENT_ID,
            "client_secret": settings.GOOGLE_CLIENT_SECRET,
            "code_verifier": code_verifier,
        }

        with httpx.Client(timeout=30) as client:
            response = client.post(token_url, data=payload)

        if response.status_code != 200:
            logger.error(
                "Erreur token Google : %d %s", response.status_code, response.text
            )
            raise ValueError(f"Échange de token Google échoué : {response.json().get('error_description', response.text)}")

        token_data = response.json()
        return self._process_token_response(token_data)

    # ─── Traitement commun des tokens ─────────────────────────────────────────

    def _process_token_response(self, token_data: dict) -> dict:
        """
        Chiffre les tokens et calcule l'expiration.
        Retourne un dict prêt à être stocké dans ConnectorConfig.
        """
        access_token = token_data.get("access_token", "")
        refresh_token = token_data.get("refresh_token", "")
        expires_in = token_data.get("expires_in", 3600)

        encrypted_access = encrypt_value(access_token) if access_token else ""
        encrypted_refresh = encrypt_value(refresh_token) if refresh_token else ""
        token_expires_at = timezone.now() + timedelta(seconds=int(expires_in))

        return {
            "oauth_access_token": encrypted_access,
            "oauth_refresh_token": encrypted_refresh,
            "token_expires_at": token_expires_at,
            "raw_access_token": access_token,
        }


oauth_service = OAuthService()
