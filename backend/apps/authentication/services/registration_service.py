"""
Service d'inscription publique — création d'organisation + compte admin.

Suit exactement le même pattern que password_reset_service.py : token signé
Django (pas de nouveau modèle de token), email HTML via email_theme.
"""
from __future__ import annotations

import logging
from typing import Optional

from django.conf import settings
from django.core import signing

logger = logging.getLogger(__name__)

VERIFY_EMAIL_SALT = "logplus_email_verification"
VERIFY_EMAIL_MAX_AGE = 24 * 60 * 60  # 24h — plus long que le reset, l'utilisateur peut traîner

INVITE_SALT = "logplus_org_invite"
INVITE_MAX_AGE = 7 * 24 * 60 * 60  # 7 jours


def generate_verify_email_token(user_id) -> str:
    return signing.dumps({"user_id": str(user_id)}, salt=VERIFY_EMAIL_SALT)


def read_verify_email_token(token: str) -> str:
    payload = signing.loads(token, salt=VERIFY_EMAIL_SALT, max_age=VERIFY_EMAIL_MAX_AGE)
    return payload["user_id"]


def generate_invite_token(user_id) -> str:
    return signing.dumps({"user_id": str(user_id)}, salt=INVITE_SALT)


def read_invite_token(token: str) -> str:
    payload = signing.loads(token, salt=INVITE_SALT, max_age=INVITE_MAX_AGE)
    return payload["user_id"]


def _frontend_url() -> str:
    return getattr(settings, "FRONTEND_URL", "http://localhost:3000").rstrip("/")


def _email_configured() -> bool:
    email_user = getattr(settings, "EMAIL_HOST_USER", "")
    backend = getattr(settings, "EMAIL_BACKEND", "django.core.mail.backends.smtp.EmailBackend")
    return bool(email_user) or "smtp" not in backend.lower()


def send_verification_email(user, organization) -> Optional[str]:
    """Envoie l'email de vérification post-inscription. Retourne le token ou None."""
    if not getattr(user, "email", None) or not _email_configured():
        if user.email:
            logger.debug("SMTP non configuré — skip email de vérification pour %s", user.email)
        return None

    from .email_theme import BORDER, MUTED, PRIMARY, TEXT, cta_button, render_email

    try:
        from django.core.mail import EmailMultiAlternatives

        token = generate_verify_email_token(user.id)
        verify_link = f"{_frontend_url()}/verify-email?token={token}"
        name = (user.first_name or user.email or "").strip()

        text_body = (
            f"Bonjour {name},\n\n"
            f"Votre organisation « {organization.name} » vient d'être créée sur Log+.\n\n"
            f"Confirmez votre adresse email pour activer votre compte administrateur "
            f"(lien valide 24h) : {verify_link}\n\n"
            f"-- Log+"
        )
        html_body_table = f"""
            <table cellpadding="0" cellspacing="0" border="0" width="100%" style="
              background:#111a2e;border:1px solid {BORDER};border-radius:16px;
              padding:26px 24px;margin-bottom:22px;text-align:center;
            ">
              <tr><td>
                <p style="margin:0 0 20px;font-size:12px;color:{MUTED};line-height:1.6;">
                  Ce lien est &#224; usage unique et expire dans <strong style="color:{TEXT};">24 heures</strong>.
                </p>
                {cta_button("Confirmer mon adresse email", verify_link, PRIMARY)}
              </td></tr>
            </table>
            <p style="margin:0;font-size:11.5px;color:{MUTED};text-align:center;word-break:break-all;">
              Si le bouton ne fonctionne pas, copiez ce lien&nbsp;: {verify_link}
            </p>
        """

        msg = EmailMultiAlternatives(
            subject="[Log+] Confirmez votre adresse email",
            body=text_body,
            from_email=getattr(settings, "DEFAULT_FROM_EMAIL", "noreply@logplus.ci"),
            to=[user.email],
        )
        msg.attach_alternative(
            render_email(
                preheader="Confirmez votre adresse email pour activer votre compte Log+.",
                badge_label="Bienvenue",
                badge_letter="L+",
                accent=PRIMARY,
                title="Confirmez votre adresse email",
                subtitle_html=(
                    f"Bonjour <strong style=\"color:{TEXT};\">{name}</strong>, votre organisation "
                    f"« <strong style=\"color:{TEXT};\">{organization.name}</strong> » vient d'être créée."
                ),
                body_html=html_body_table,
                warning_html="Si vous n'êtes pas à l'origine de cette inscription, ignorez cet email.",
            ),
            "text/html",
        )
        msg.send(fail_silently=False)
        return token
    except Exception as exc:
        logger.warning("registration_service: envoi email echoue pour %s: %s", user.email, exc)
        return None


def send_invite_email(user, organization, inviter) -> Optional[str]:
    """Envoie l'email d'invitation d'un nouveau membre par un admin d'organisation."""
    if not getattr(user, "email", None) or not _email_configured():
        return None

    from .email_theme import BORDER, MUTED, PRIMARY, TEXT, cta_button, render_email

    try:
        from django.core.mail import EmailMultiAlternatives

        token = generate_invite_token(user.id)
        invite_link = f"{_frontend_url()}/invite?token={token}"
        name = (user.first_name or user.email or "").strip()
        inviter_name = (inviter.full_name or inviter.email or "").strip()

        text_body = (
            f"Bonjour {name},\n\n"
            f"{inviter_name} vous invite à rejoindre l'organisation « {organization.name} » sur Log+.\n\n"
            f"Définissez votre mot de passe (lien valide 7 jours) : {invite_link}\n\n"
            f"-- Log+"
        )
        html_body_table = f"""
            <table cellpadding="0" cellspacing="0" border="0" width="100%" style="
              background:#111a2e;border:1px solid {BORDER};border-radius:16px;
              padding:26px 24px;margin-bottom:22px;text-align:center;
            ">
              <tr><td>
                <p style="margin:0 0 20px;font-size:12px;color:{MUTED};line-height:1.6;">
                  Ce lien est &#224; usage unique et expire dans <strong style="color:{TEXT};">7 jours</strong>.
                </p>
                {cta_button("Définir mon mot de passe", invite_link, PRIMARY)}
              </td></tr>
            </table>
            <p style="margin:0;font-size:11.5px;color:{MUTED};text-align:center;word-break:break-all;">
              Si le bouton ne fonctionne pas, copiez ce lien&nbsp;: {invite_link}
            </p>
        """

        msg = EmailMultiAlternatives(
            subject=f"[Log+] Invitation à rejoindre {organization.name}",
            body=text_body,
            from_email=getattr(settings, "DEFAULT_FROM_EMAIL", "noreply@logplus.ci"),
            to=[user.email],
        )
        msg.attach_alternative(
            render_email(
                preheader=f"{inviter_name} vous invite à rejoindre {organization.name} sur Log+.",
                badge_label="Invitation",
                badge_letter="L+",
                accent=PRIMARY,
                title="Vous êtes invité(e) sur Log+",
                subtitle_html=(
                    f"<strong style=\"color:{TEXT};\">{inviter_name}</strong> vous invite à rejoindre "
                    f"« <strong style=\"color:{TEXT};\">{organization.name}</strong> »."
                ),
                body_html=html_body_table,
                warning_html="Si vous ne vous attendiez pas à cette invitation, ignorez cet email.",
            ),
            "text/html",
        )
        msg.send(fail_silently=False)
        return token
    except Exception as exc:
        logger.warning("registration_service: envoi invite echoue pour %s: %s", user.email, exc)
        return None
