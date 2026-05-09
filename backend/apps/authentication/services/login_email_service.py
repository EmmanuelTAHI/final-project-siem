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

OTP_TTL_SECONDS = 60 * 60  # 1 h


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
                 primary_color: str = "#0057FF") -> str:
    name = (user.first_name or user.email or "").strip()
    front = _frontend_url()
    ip_display = ip or "—"
    ua_display = ua or "—"
    return (
        f'<!doctype html><html lang="fr"><head>'
        f'<meta charset="utf-8"/>'
        f'<title>{title}</title>'
        f'</head><body style="margin:0;padding:24px;background:#0B1020;color:#E5E9F2;'
        f'font-family:-apple-system,Segoe UI,Roboto,sans-serif;">'
        f'<div style="max-width:560px;margin:0 auto;background:#111A30;'
        f'border:1px solid #1E2A47;border-radius:14px;overflow:hidden;">'
        f'<div style="padding:18px 22px;border-bottom:1px solid #1E2A47;">'
        f'<span style="font-size:11px;letter-spacing:0.1em;color:#8B9EC7;'
        f'text-transform:uppercase;font-weight:600;">Log+</span>'
        f'</div>'
        f'<div style="padding:24px 22px;">'
        f'<h1 style="font-size:20px;margin:0 0 8px 0;color:#FFFFFF;">{title}</h1>'
        f'<p style="margin:0 0 16px;color:#B5C0D9;font-size:14px;line-height:1.55;">'
        f'Bonjour {name},<br/>{intro}'
        f'</p>'
        f'<div style="background:#0B1226;border:1px solid #243054;border-radius:10px;'
        f'padding:16px;margin:16px 0;text-align:center;">'
        f'<div style="font-size:11px;color:#8B9EC7;margin-bottom:8px;'
        f'text-transform:uppercase;letter-spacing:0.1em;">Code de vérification (valide 1 h)</div>'
        f'<div style="font-family:monospace;font-size:30px;font-weight:700;'
        f'letter-spacing:8px;color:#FFFFFF;padding:8px 0;">{otp}</div>'
        f'</div>'
        f'<table style="width:100%;font-size:13px;color:#B5C0D9;border-collapse:collapse;">'
        f'<tr><td style="padding:5px 0;color:#8B9EC7;width:130px;">Méthode</td>'
        f'<td>{method}</td></tr>'
        f'<tr><td style="padding:5px 0;color:#8B9EC7;">Survenu</td>'
        f'<td>{when_iso}</td></tr>'
        f'<tr><td style="padding:5px 0;color:#8B9EC7;">Adresse IP</td>'
        f'<td><code>{ip_display}</code></td></tr>'
        f'<tr><td style="padding:5px 0;color:#8B9EC7;">Navigateur</td>'
        f'<td>{ua_display}</td></tr>'
        f'</table>'
        f'<div style="margin-top:24px;text-align:center;">'
        f'<a href="{front}/dashboard" style="display:inline-block;'
        f'background:{primary_color};color:#FFFFFF;text-decoration:none;'
        f'padding:11px 22px;border-radius:8px;font-weight:600;font-size:14px;">'
        f'Ouvrir Log+'
        f'</a></div>'
        f'<p style="font-size:11.5px;color:#6B7BA0;margin-top:24px;text-align:center;">'
        f'Si ce n\'est pas vous, changez votre mot de passe immédiatement.'
        f'</p>'
        f'</div></div></body></html>'
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
