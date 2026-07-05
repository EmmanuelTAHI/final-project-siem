"""
Service de réinitialisation de mot de passe.
Génère un lien signé (valide 30 min) envoyé par email, indépendant de l'OTP de connexion.
"""
from __future__ import annotations

import logging
from typing import Optional

from django.conf import settings
from django.core import signing

logger = logging.getLogger(__name__)

RESET_TOKEN_SALT = "logplus_password_reset"
RESET_TOKEN_MAX_AGE = 30 * 60  # 30 min


def generate_reset_token(user_id) -> str:
    return signing.dumps({"user_id": str(user_id)}, salt=RESET_TOKEN_SALT)


def read_reset_token(token: str) -> str:
    """Retourne le user_id encodé dans le token. Lève SignatureExpired / BadSignature."""
    payload = signing.loads(token, salt=RESET_TOKEN_SALT, max_age=RESET_TOKEN_MAX_AGE)
    return payload["user_id"]


def _frontend_url() -> str:
    return getattr(settings, "FRONTEND_URL", "http://localhost:3000").rstrip("/")


def _render_html(user, reset_link: str) -> str:
    name = (user.first_name or user.email or "").strip()
    return (
        f'<!doctype html><html lang="fr"><head><meta charset="utf-8"/>'
        f'<title>Réinitialisation du mot de passe</title></head>'
        f'<body style="margin:0;padding:24px;background:#0B1020;color:#E5E9F2;'
        f'font-family:-apple-system,Segoe UI,Roboto,sans-serif;">'
        f'<div style="max-width:560px;margin:0 auto;background:#111A30;'
        f'border:1px solid #1E2A47;border-radius:14px;overflow:hidden;">'
        f'<div style="padding:18px 22px;border-bottom:1px solid #1E2A47;">'
        f'<span style="font-size:11px;letter-spacing:0.1em;color:#8B9EC7;'
        f'text-transform:uppercase;font-weight:600;">Log+</span></div>'
        f'<div style="padding:24px 22px;">'
        f'<h1 style="font-size:20px;margin:0 0 8px 0;color:#FFFFFF;">'
        f'Réinitialisation de votre mot de passe</h1>'
        f'<p style="margin:0 0 20px;color:#B5C0D9;font-size:14px;line-height:1.55;">'
        f'Bonjour {name},<br/>Une demande de réinitialisation de mot de passe a été '
        f'effectuée pour votre compte Log+. Ce lien est valide 30 minutes. '
        f'Si vous n\'êtes pas à l\'origine de cette demande, ignorez cet email.'
        f'</p>'
        f'<div style="text-align:center;margin:24px 0;">'
        f'<a href="{reset_link}" style="display:inline-block;background:#0057FF;'
        f'color:#FFFFFF;text-decoration:none;padding:11px 22px;border-radius:8px;'
        f'font-weight:600;font-size:14px;">Réinitialiser mon mot de passe</a></div>'
        f'<p style="font-size:11.5px;color:#6B7BA0;margin-top:24px;text-align:center;">'
        f'Si le bouton ne fonctionne pas, copiez ce lien : {reset_link}'
        f'</p>'
        f'</div></div></body></html>'
    )


def send_password_reset_email(user) -> Optional[str]:
    """Envoie l'email de réinitialisation. Retourne le token ou None si non envoyé."""
    if not getattr(user, "email", None):
        return None

    email_user = getattr(settings, "EMAIL_HOST_USER", "")
    backend = getattr(settings, "EMAIL_BACKEND", "django.core.mail.backends.smtp.EmailBackend")
    if not email_user and "smtp" in backend.lower():
        logger.debug("SMTP non configuré — skip email de reset pour %s", user.email)
        return None

    try:
        from django.core.mail import EmailMultiAlternatives

        token = generate_reset_token(user.id)
        reset_link = f"{_frontend_url()}/reset-password?token={token}"

        text_body = (
            f"Bonjour {user.first_name or user.email},\n\n"
            f"Une demande de réinitialisation de mot de passe a été effectuée "
            f"pour votre compte Log+.\n\n"
            f"Lien de réinitialisation (valide 30 min) : {reset_link}\n\n"
            f"Si vous n'êtes pas à l'origine de cette demande, ignorez cet email.\n\n"
            f"-- Log+"
        )
        msg = EmailMultiAlternatives(
            subject="[Log+] Réinitialisation de votre mot de passe",
            body=text_body,
            from_email=getattr(settings, "DEFAULT_FROM_EMAIL", "noreply@logplus.ci"),
            to=[user.email],
        )
        msg.attach_alternative(_render_html(user, reset_link), "text/html")
        msg.send(fail_silently=False)
        return token
    except Exception as exc:
        logger.warning("password_reset_service: envoi email echoue pour %s: %s", user.email, exc)
        return None
