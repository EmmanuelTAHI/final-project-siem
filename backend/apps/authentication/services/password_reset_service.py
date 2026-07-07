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
    from .email_theme import BORDER, MUTED, PRIMARY, TEXT, cta_button, render_email

    name = (user.first_name or user.email or "").strip()

    body = f"""
            <table cellpadding="0" cellspacing="0" border="0" width="100%" style="
              background:#111a2e;border:1px solid {BORDER};border-radius:16px;
              padding:26px 24px;margin-bottom:22px;text-align:center;
            ">
              <tr><td>
                <p style="margin:0 0 20px;font-size:12px;color:{MUTED};line-height:1.6;">
                  Ce lien est &#224; usage unique et expire dans <strong style="color:{TEXT};">30 minutes</strong>.
                </p>
                {cta_button("Réinitialiser mon mot de passe", reset_link, PRIMARY)}
              </td></tr>
            </table>
            <p style="margin:0;font-size:11.5px;color:{MUTED};text-align:center;word-break:break-all;">
              Si le bouton ne fonctionne pas, copiez ce lien&nbsp;: {reset_link}
            </p>
    """

    return render_email(
        preheader="Réinitialisation de votre mot de passe Log+ — lien valide 30 minutes.",
        badge_label="Compte & sécurité",
        badge_letter="L+",
        accent=PRIMARY,
        title="Réinitialisation de votre mot de passe",
        subtitle_html=(
            f"Bonjour <strong style=\"color:{TEXT};\">{name}</strong>, une demande de réinitialisation "
            "de mot de passe a été effectuée pour votre compte Log+."
        ),
        body_html=body,
        warning_html="Si vous n'êtes pas à l'origine de cette demande, ignorez cet email — votre mot de passe restera inchangé.",
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
