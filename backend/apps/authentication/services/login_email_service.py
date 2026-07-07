"""
Service d'envoi d'emails de confirmation de connexion (mot de passe + OAuth).
Génère un OTP 6 chiffres, envoyé par email lors de chaque connexion.
"""
from __future__ import annotations

import logging
import secrets
from typing import Optional

from django.conf import settings
from django.utils import timezone

logger = logging.getLogger(__name__)

OTP_TTL_SECONDS = 10 * 60  # 10 min — code expiré après 10 minutes


def _otp_key(user_id) -> str:
    return f"login_otp:{user_id}"


def _get_cache():
    """Import lazy pour éviter tout problème d'initialisation au démarrage Django."""
    from django.core.cache import cache
    return cache


def generate_login_otp(user_id) -> str:
    otp = f"{secrets.randbelow(1_000_000):06d}"
    _get_cache().set(_otp_key(user_id), otp, OTP_TTL_SECONDS)
    return otp


def verify_login_otp(user_id, otp: str) -> bool:
    cache = _get_cache()
    expected = cache.get(_otp_key(user_id))
    if expected and secrets.compare_digest(str(expected), str(otp).strip()):
        cache.delete(_otp_key(user_id))
        return True
    return False


def _frontend_url() -> str:
    return getattr(settings, "FRONTEND_URL", "http://localhost:3000").rstrip("/")


def _render_html(user, title: str, intro: str, otp: str, method: str,
                 ip: str, ua: str, when_iso: str,
                 primary_color: str = None) -> str:
    from . import email_theme as t

    name = (user.first_name or user.email or "").strip()
    accent = primary_color or t.PRIMARY
    ip_display = ip or "—"
    ua_display = (ua[:70] + "…") if ua and len(ua) > 70 else (ua or "—")

    body = f"""
            <table cellpadding="0" cellspacing="0" border="0" width="100%" style="
              background:#111a2e;border:1px solid {t.BORDER};border-radius:16px;margin-bottom:20px;
            ">
              <tr><td style="padding:26px 24px;">
                <p style="margin:0 0 18px;font-size:11px;font-weight:700;color:{t.MUTED};
                   letter-spacing:0.12em;text-transform:uppercase;text-align:center;">
                  Code de v&#233;rification
                </p>
                {t.digit_boxes(otp, accent)}
                <table cellpadding="0" cellspacing="0" border="0" width="100%" style="margin:18px 0;">
                  <tr><td style="border-bottom:1px solid {t.BORDER};font-size:0;">&nbsp;</td></tr>
                </table>
                <table cellpadding="0" cellspacing="0" border="0" align="center">
                  <tr><td style="background:{accent}18;border:1px solid {accent}33;border-radius:20px;
                    padding:6px 18px;font-size:12px;font-weight:700;color:{accent};text-align:center;">
                    &#9201;&nbsp; Valable <strong>10&nbsp;minutes</strong>
                  </td></tr>
                </table>
              </td></tr>
            </table>
            {t.metadata_table([
                ("Méthode", method),
                ("Survenu", when_iso),
                ("Adresse IP", f"<code>{ip_display}</code>"),
                ("Navigateur", ua_display),
            ])}
            {t.cta_button("Ouvrir Log+", f"{_frontend_url()}/dashboard", accent)}
    """

    return t.render_email(
        preheader=f"Code de vérification Log+ : {otp} — valable 10 minutes.",
        badge_label="Connexion au SOC",
        badge_letter="L+",
        accent=accent,
        title=title,
        subtitle_html=f"Bonjour <strong style=\"color:{t.TEXT};\">{name}</strong>, {intro}",
        body_html=body,
        warning_html="Si ce n'est pas vous, changez votre mot de passe immédiatement et révoquez vos sessions actives depuis Log+.",
    )


def send_login_confirmation(
    user,
    *,
    method: str = "Mot de passe",
    ip: str = "",
    user_agent: str = "",
    extra_intro: Optional[str] = None,
) -> Optional[str]:
    """Envoie email confirmation + OTP. Retourne l'OTP ou None si non envoyé."""
    if not getattr(user, "email", None):
        return None

    # Ne pas tenter si SMTP non configuré
    email_host = getattr(settings, "EMAIL_HOST", "localhost")
    email_user = getattr(settings, "EMAIL_HOST_USER", "")
    backend = getattr(settings, "EMAIL_BACKEND", "django.core.mail.backends.smtp.EmailBackend")
    if not email_user and "smtp" in backend.lower():
        logger.debug("SMTP non configure (EMAIL_HOST_USER vide) — skip email pour %s", user.email)
        return None

    try:
        from django.core.mail import EmailMultiAlternatives

        otp = generate_login_otp(user.id)
        when = timezone.now().strftime("%Y-%m-%d %H:%M:%S UTC")
        intro = extra_intro or (
            "Une connexion vient d'être effectuée sur votre compte Log+. "
            "Si c'est bien vous, aucune action n'est requise."
        )
        title = "Connexion à Log+ confirmée"

        text_body = (
            f"Bonjour {user.first_name or user.email},\n\n"
            f"{intro}\n\n"
            f"Code OTP (valide 1h) : {otp}\n\n"
            f"Methode : {method}\n"
            f"Survenu : {when}\n"
            f"IP : {ip or '-'}\n"
            f"Navigateur : {user_agent[:80] or '-'}\n\n"
            f"-- Log+"
        )
        html_body = _render_html(
            user=user, title=title, intro=intro, otp=otp,
            method=method, ip=ip, ua=user_agent[:120], when_iso=when,
        )

        msg = EmailMultiAlternatives(
            subject=f"[Log+] {title}",
            body=text_body,
            from_email=getattr(settings, "DEFAULT_FROM_EMAIL", "noreply@logplus.ci"),
            to=[user.email],
        )
        msg.attach_alternative(html_body, "text/html")
        msg.send(fail_silently=False)
        return otp
    except Exception as exc:
        logger.warning("login_email_service: envoi email echoue pour %s: %s", user.email, exc)
        return None
