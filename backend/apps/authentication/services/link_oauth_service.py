"""
Flow OAuth2 PKCE pour la liaison de comptes personnels (Google / Microsoft / GitHub).

Distinct du flow d'ingestion des connecteurs M365/Workspace (oauth_service.py) :

- Le state Redis contient { user_id, provider, code_verifier } pour qu'au callback
  on sache à quel utilisateur lier le compte (le callback est AllowAny pour permettre
  la redirection IdP).
- Au callback on récupère aussi le profil utilisateur (id, email, nom, avatar) et on
  crée/met à jour un LinkedAccount.
- Les scopes demandés sont ceux nécessaires au monitoring de l'activité de connexion :
  * Google     : profile + email + admin.reports.audit.readonly (login activity)
  * Microsoft  : User.Read + AuditLog.Read.All
  * GitHub     : read:user + user:email
"""
import base64
import hashlib
import json
import logging
import re
import secrets
from dataclasses import dataclass
from datetime import timedelta
from typing import Optional
from urllib.parse import urlencode

import httpx
from django.conf import settings
from django.core.cache import cache
from django.utils import timezone

from utils.encryption import decrypt_value, encrypt_value

from ..models import LinkedAccount

logger = logging.getLogger(__name__)

OAUTH_LINK_STATE_TTL = 600  # 10 minutes
LINK_STATE_PREFIX = "oauth_link_state:"


def _decode_microsoft_upn(upn: str) -> str:
    """
    Microsoft guest accounts have UPNs like:
        emmanueltahi14_gmail.com#EXT#@tenant.onmicrosoft.com

    The real email is encoded before the #EXT# marker:
        emmanueltahi14_gmail.com  →  emmanueltahi14@gmail.com
    (the last underscore before a domain suffix replaces the @)
    """
    if not upn or "#EXT#" not in upn:
        return upn
    local = upn.split("#EXT#")[0]
    match = re.match(r"^(.+)_([A-Za-z0-9.-]+\.[A-Za-z]{2,})$", local)
    if match:
        return f"{match.group(1)}@{match.group(2)}"
    return upn


@dataclass
class ProviderProfile:
    provider_user_id: str
    email: str
    display_name: str
    avatar_url: str = ""


@dataclass
class TokenBundle:
    access_token: str
    refresh_token: str
    expires_in: int
    scopes: str = ""


# ─────────────────────────────────────────────────────────────────────────────
# PKCE helpers
# ─────────────────────────────────────────────────────────────────────────────


def _generate_code_verifier() -> str:
    return base64.urlsafe_b64encode(secrets.token_bytes(96)).rstrip(b"=").decode("utf-8")


def _generate_code_challenge(verifier: str) -> str:
    digest = hashlib.sha256(verifier.encode("utf-8")).digest()
    return base64.urlsafe_b64encode(digest).rstrip(b"=").decode("utf-8")


def _generate_state() -> str:
    return secrets.token_hex(32)


def _store_link_state(state: str, payload: dict) -> None:
    try:
        cache.set(LINK_STATE_PREFIX + state, json.dumps(payload), timeout=OAUTH_LINK_STATE_TTL)
    except Exception as exc:
        logger.error("Cache Redis indisponible pour stocker l'état OAuth : %s", exc)
        raise ValueError(
            "Le service de cache (Redis) est indisponible. "
            "Assurez-vous que Redis est lancé : redis-server"
        ) from exc


def _pop_link_state(state: str) -> Optional[dict]:
    key = LINK_STATE_PREFIX + state
    try:
        raw = cache.get(key)
    except Exception as exc:
        logger.error("Cache Redis indisponible pour lire l'état OAuth : %s", exc)
        return None
    if not raw:
        return None
    cache.delete(key)
    try:
        return json.loads(raw)
    except (TypeError, ValueError):
        return None


# ─────────────────────────────────────────────────────────────────────────────
# Provider configs
# ─────────────────────────────────────────────────────────────────────────────


def _google_link_config():
    return {
        "auth_url": "https://accounts.google.com/o/oauth2/v2/auth",
        "token_url": "https://oauth2.googleapis.com/token",
        "userinfo_url": "https://www.googleapis.com/oauth2/v3/userinfo",
        "client_id": settings.GOOGLE_CLIENT_ID,
        "client_secret": settings.GOOGLE_CLIENT_SECRET,
        "redirect_uri": getattr(
            settings,
            "GOOGLE_LINK_REDIRECT_URI",
            f"{getattr(settings, 'BACKEND_URL', 'http://localhost:8000')}/api/auth/oauth/link/google/callback/",
        ),
        # Scopes de base uniquement — pas d'admin SDK qui nécessite Workspace admin
        "scopes": ["openid", "email", "profile"],
        "extra_params": {"access_type": "offline", "prompt": "consent"},
    }


def _microsoft_link_config():
    tenant = getattr(settings, "MICROSOFT_TENANT_ID", "common") or "common"
    return {
        "auth_url": f"https://login.microsoftonline.com/{tenant}/oauth2/v2.0/authorize",
        "token_url": f"https://login.microsoftonline.com/{tenant}/oauth2/v2.0/token",
        "userinfo_url": "https://graph.microsoft.com/v1.0/me",
        "client_id": settings.MICROSOFT_CLIENT_ID,
        "client_secret": settings.MICROSOFT_CLIENT_SECRET,
        "redirect_uri": getattr(
            settings,
            "MICROSOFT_LINK_REDIRECT_URI",
            f"{getattr(settings, 'BACKEND_URL', 'http://localhost:8000')}/api/auth/oauth/link/microsoft/callback/",
        ),
        "scopes": [
            "openid",
            "profile",
            "email",
            "offline_access",
            "User.Read",
            "AuditLog.Read.All",
        ],
        "extra_params": {"response_mode": "query"},
    }


def _github_link_config():
    return {
        "auth_url": "https://github.com/login/oauth/authorize",
        "token_url": "https://github.com/login/oauth/access_token",
        "userinfo_url": "https://api.github.com/user",
        "emails_url": "https://api.github.com/user/emails",
        "client_id": getattr(settings, "GITHUB_CLIENT_ID", ""),
        "client_secret": getattr(settings, "GITHUB_CLIENT_SECRET", ""),
        "redirect_uri": getattr(
            settings,
            "GITHUB_LINK_REDIRECT_URI",
            f"{getattr(settings, 'BACKEND_URL', 'http://localhost:8000')}/api/auth/oauth/link/github/callback/",
        ),
        "scopes": ["read:user", "user:email"],
        "extra_params": {},
    }


_PROVIDERS = {
    "google": _google_link_config,
    "microsoft": _microsoft_link_config,
    "github": _github_link_config,
}

# Nom de la variable d'env à citer dans le message d'erreur, par provider.
_CLIENT_ID_ENV_VAR = {
    "google": "GOOGLE_CLIENT_ID",
    "microsoft": "MICROSOFT_CLIENT_ID",
    "github": "GITHUB_CLIENT_ID",
}


# ─────────────────────────────────────────────────────────────────────────────
# Public API
# ─────────────────────────────────────────────────────────────────────────────


class LinkOAuthService:
    """Service de liaison OAuth pour comptes personnels."""

    SUPPORTED = list(_PROVIDERS.keys())

    def initiate(self, provider: str, user_id: str) -> dict:
        if provider not in _PROVIDERS:
            raise ValueError(f"Provider non supporté : {provider}")

        cfg = _PROVIDERS[provider]()
        if not cfg["client_id"]:
            env_var = _CLIENT_ID_ENV_VAR.get(provider, f"{provider.upper()}_CLIENT_ID")
            raise ValueError(
                f"Le provider '{provider}' n'est pas configuré sur ce serveur "
                f"({env_var} manquant dans .env). "
                f"Ajoutez les credentials {provider.capitalize()} dans la configuration."
            )

        verifier = _generate_code_verifier()
        challenge = _generate_code_challenge(verifier)
        state = _generate_state()

        _store_link_state(state, {
            "user_id": str(user_id),
            "provider": provider,
            "code_verifier": verifier,
        })

        params = {
            "response_type": "code",
            "client_id": cfg["client_id"],
            "redirect_uri": cfg["redirect_uri"],
            "scope": " ".join(cfg["scopes"]),
            "state": state,
            **cfg["extra_params"],
        }
        # GitHub ne supporte pas le PKCE pour les apps standard — on s'appuie sur le state.
        if provider != "github":
            params["code_challenge"] = challenge
            params["code_challenge_method"] = "S256"

        return {
            "authorization_url": f"{cfg['auth_url']}?{urlencode(params)}",
            "state": state,
            "provider": provider,
        }

    def callback_with_pin(self, provider: str, code: str, state: str):
        """
        Échange le code OAuth, récupère le profil, crée un AccountLinkVerification
        avec un PIN 4 chiffres, envoie l'email de vérification.
        Retourne l'objet AccountLinkVerification.
        """
        from datetime import timedelta as td
        from apps.users.models import User
        from apps.authentication.models import AccountLinkVerification
        from apps.authentication.services.email_pin_service import generate_pin, send_pin_email

        if provider not in _PROVIDERS:
            raise ValueError(f"Provider non supporté : {provider}")
        payload = _pop_link_state(state)
        if not payload:
            raise ValueError("State OAuth invalide ou expiré.")
        if payload.get("provider") != provider:
            raise ValueError("Provider du state ne correspond pas.")

        cfg = _PROVIDERS[provider]()
        tokens = self._exchange_code(provider, cfg, code, payload["code_verifier"])
        profile = self._fetch_profile(provider, cfg, tokens.access_token)

        user = User.objects.get(pk=payload["user_id"])

        # Invalider les vérifications précédentes non utilisées pour ce provider/user
        AccountLinkVerification.objects.filter(
            user=user, provider=provider, is_used=False
        ).update(is_used=True)

        pin = generate_pin()
        verification = AccountLinkVerification.objects.create(
            user=user,
            provider=provider,
            provider_email=profile.email,
            provider_user_id=profile.provider_user_id,
            provider_display_name=profile.display_name,
            avatar_url=profile.avatar_url,
            oauth_data={
                "access_token_encrypted": encrypt_value(tokens.access_token) if tokens.access_token else "",
                "refresh_token_encrypted": encrypt_value(tokens.refresh_token) if tokens.refresh_token else "",
                "expires_in": int(tokens.expires_in or 3600),
                "scopes": tokens.scopes,
            },
            pin=pin,
            expires_at=timezone.now() + td(minutes=5),
        )

        send_pin_email(
            to_email=profile.email,
            provider=provider,
            provider_display_name=profile.display_name,
            logplus_user_email=user.email,
            pin=pin,
        )

        return verification

    def finalize_link(self, verification) -> LinkedAccount:
        """Crée le LinkedAccount à partir d'une AccountLinkVerification validée."""
        from apps.users.models import User

        user = verification.user
        data = verification.oauth_data

        linked, _ = LinkedAccount.objects.update_or_create(
            user=user,
            provider=verification.provider,
            provider_user_id=verification.provider_user_id,
            defaults={
                "provider_email": verification.provider_email,
                "provider_display_name": verification.provider_display_name,
                "avatar_url": verification.avatar_url,
                "access_token_encrypted": data.get("access_token_encrypted", ""),
                "refresh_token_encrypted": data.get("refresh_token_encrypted", ""),
                "token_expires_at": timezone.now() + timedelta(seconds=int(data.get("expires_in", 3600))),
                "scopes": data.get("scopes", ""),
                "status": "active",
            },
        )
        verification.is_used = True
        verification.save(update_fields=["is_used"])
        return linked

    def get_access_token(self, account: LinkedAccount) -> str:
        """Renvoie un access_token déchiffré, en rafraîchissant si expiré."""
        if account.token_expires_at and account.token_expires_at <= timezone.now() + timedelta(minutes=2):
            self._refresh(account)
            account.refresh_from_db()
        return decrypt_value(account.access_token_encrypted)

    # ─── Internal: token exchange ─────────────────────────────────────────────

    def _exchange_code(self, provider: str, cfg: dict, code: str, code_verifier: str) -> TokenBundle:
        data = {
            "grant_type": "authorization_code",
            "code": code,
            "redirect_uri": cfg["redirect_uri"],
            "client_id": cfg["client_id"],
            "client_secret": cfg["client_secret"],
        }
        if provider != "github":
            data["code_verifier"] = code_verifier

        headers = {"Accept": "application/json"} if provider == "github" else {}

        with httpx.Client(timeout=30) as client:
            resp = client.post(cfg["token_url"], data=data, headers=headers)
        if resp.status_code != 200:
            logger.error("Token exchange failed (%s): %d %s", provider, resp.status_code, resp.text)
            raise ValueError(f"Échange de token {provider} échoué : {resp.text[:200]}")
        body = resp.json()
        if "error" in body:
            raise ValueError(f"Erreur OAuth {provider} : {body.get('error_description', body.get('error'))}")

        return TokenBundle(
            access_token=body.get("access_token", ""),
            refresh_token=body.get("refresh_token", ""),
            expires_in=int(body.get("expires_in") or 0) or 3600,
            scopes=body.get("scope", "") or " ".join(cfg["scopes"]),
        )

    def _refresh(self, account: LinkedAccount) -> None:
        if not account.refresh_token_encrypted:
            account.status = "error"
            account.save(update_fields=["status", "updated_at"])
            raise ValueError("Pas de refresh_token : reliez le compte.")

        cfg = _PROVIDERS[account.provider]()
        refresh_token = decrypt_value(account.refresh_token_encrypted)
        data = {
            "grant_type": "refresh_token",
            "refresh_token": refresh_token,
            "client_id": cfg["client_id"],
            "client_secret": cfg["client_secret"],
        }
        headers = {"Accept": "application/json"} if account.provider == "github" else {}

        with httpx.Client(timeout=30) as client:
            resp = client.post(cfg["token_url"], data=data, headers=headers)
        if resp.status_code != 200:
            account.status = "error"
            account.save(update_fields=["status", "updated_at"])
            raise ValueError(f"Refresh {account.provider} échoué : {resp.text[:200]}")
        body = resp.json()

        account.access_token_encrypted = encrypt_value(body.get("access_token", ""))
        if body.get("refresh_token"):
            account.refresh_token_encrypted = encrypt_value(body["refresh_token"])
        account.token_expires_at = timezone.now() + timedelta(
            seconds=int(body.get("expires_in") or 3600)
        )
        account.status = "active"
        account.save(update_fields=[
            "access_token_encrypted", "refresh_token_encrypted",
            "token_expires_at", "status", "updated_at",
        ])

    # ─── Internal: profile fetch ──────────────────────────────────────────────

    def _fetch_profile(self, provider: str, cfg: dict, access_token: str) -> ProviderProfile:
        if provider == "google":
            return self._fetch_google_profile(cfg, access_token)
        if provider == "microsoft":
            return self._fetch_microsoft_profile(cfg, access_token)
        if provider == "github":
            return self._fetch_github_profile(cfg, access_token)
        raise ValueError(provider)

    def _fetch_google_profile(self, cfg, token):
        with httpx.Client(timeout=15) as client:
            r = client.get(cfg["userinfo_url"], headers={"Authorization": f"Bearer {token}"})
        r.raise_for_status()
        d = r.json()
        return ProviderProfile(
            provider_user_id=str(d.get("sub") or d.get("id") or ""),
            email=d.get("email", ""),
            display_name=d.get("name") or d.get("email", ""),
            avatar_url=d.get("picture", ""),
        )

    def _fetch_microsoft_profile(self, cfg, token):
        # Request otherMails in addition to standard fields — needed for guest/external accounts
        url = cfg["userinfo_url"] + "?$select=id,displayName,mail,userPrincipalName,otherMails"
        with httpx.Client(timeout=15) as client:
            r = client.get(url, headers={"Authorization": f"Bearer {token}"})
        r.raise_for_status()
        d = r.json()

        email = (
            d.get("mail")
            or (d.get("otherMails") or [None])[0]
            or _decode_microsoft_upn(d.get("userPrincipalName", ""))
        )

        return ProviderProfile(
            provider_user_id=str(d.get("id") or ""),
            email=email,
            display_name=d.get("displayName") or email,
            avatar_url="",
        )

    def _fetch_github_profile(self, cfg, token):
        headers = {"Authorization": f"Bearer {token}", "Accept": "application/vnd.github+json"}
        with httpx.Client(timeout=15) as client:
            r = client.get(cfg["userinfo_url"], headers=headers)
            r.raise_for_status()
            d = r.json()
            email = d.get("email") or ""
            if not email:
                er = client.get(cfg["emails_url"], headers=headers)
                if er.status_code == 200:
                    primary = next((e for e in er.json() if e.get("primary")), None)
                    email = (primary or {}).get("email", "")
        return ProviderProfile(
            provider_user_id=str(d.get("id") or ""),
            email=email,
            display_name=d.get("name") or d.get("login", ""),
            avatar_url=d.get("avatar_url", ""),
        )


link_oauth_service = LinkOAuthService()
