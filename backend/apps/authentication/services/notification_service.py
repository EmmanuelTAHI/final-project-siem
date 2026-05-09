"""
Service de notifications de sécurité (Comptes liés).

Trois canaux :
- Persistance      : SecurityNotification en base (alimente la cloche dans la topbar).
- WebSocket        : push temps réel via le channel layer (group user_<id>).
- Email            : alerte avec lien signé "C'est moi / Pas moi".

Les confirmations utilisent django.core.signing (TimestampSigner) — pas de table token
en plus, on signe juste l'UUID de la LoginConfirmation.
"""
import logging
from datetime import timedelta
from typing import Optional

from asgiref.sync import async_to_sync
from channels.layers import get_channel_layer
from django.conf import settings
from django.core import signing
from django.core.mail import EmailMultiAlternatives
from django.utils import timezone

from ..models import LinkedAccount, LoginConfirmation, ProviderLoginEvent, SecurityNotification

logger = logging.getLogger(__name__)

CONFIRM_TOKEN_SALT = "logplus.login_confirmation"
CONFIRM_TOKEN_MAX_AGE = 60 * 60 * 24  # 24h


# ─────────────────────────────────────────────────────────────────────────────
# Signed tokens
# ─────────────────────────────────────────────────────────────────────────────


def make_confirmation_token(confirmation_id) -> str:
    return signing.dumps(str(confirmation_id), salt=CONFIRM_TOKEN_SALT)


def read_confirmation_token(token: str) -> str:
    """Renvoie l'UUID décodé. Lève signing.BadSignature / SignatureExpired."""
    return signing.loads(token, salt=CONFIRM_TOKEN_SALT, max_age=CONFIRM_TOKEN_MAX_AGE)


# ─────────────────────────────────────────────────────────────────────────────
# Dispatch
# ─────────────────────────────────────────────────────────────────────────────


def _push_websocket(user_id, payload: dict) -> None:
    layer = get_channel_layer()
    if not layer:
        return
    try:
        async_to_sync(layer.group_send)(
            f"user_{user_id}",
            {"type": "system.notification", "notification": payload},
        )
    except Exception as exc:
        logger.warning("WS push failed: %s", exc)


def _frontend_url() -> str:
    return getattr(settings, "FRONTEND_URL", "http://localhost:3000").rstrip("/")


def _send_email(notif: SecurityNotification, confirmation: Optional[LoginConfirmation]) -> None:
    user = notif.user
    if not user.email:
        return

    confirm_url = ""
    deny_url = ""
    if confirmation:
        token = make_confirmation_token(confirmation.id)
        base = f"{_frontend_url()}/confirm-login/{token}"
        confirm_url = f"{base}?action=approve"
        deny_url = f"{base}?action=reject"

    md = notif.metadata or {}
    device_line = " · ".join(filter(None, [md.get("browser"), md.get("os"), md.get("device_type")]))
    geo_line = " · ".join(filter(None, [md.get("geo_city"), md.get("geo_country")]))

    text_body = (
        f"Bonjour {user.first_name or user.email},\n\n"
        f"{notif.title}\n\n"
        f"{notif.body}\n\n"
        f"Appareil  : {device_line or 'inconnu'}\n"
        f"Adresse IP: {md.get('ip_address') or 'n/a'}\n"
        f"Lieu      : {geo_line or 'inconnu'}\n"
        f"Service   : {md.get('provider') or 'n/a'} ({md.get('provider_email') or ''})\n\n"
    )
    if confirmation:
        text_body += (
            f"Si c'est bien vous   → {confirm_url}\n"
            f"Si ce n'est pas vous → {deny_url}\n\n"
            "Si ce n'est pas vous, nous révoquerons immédiatement la session côté provider.\n"
        )

    text_body += "\n— Log+"

    html_body = _render_html_email(user, notif, md, device_line, geo_line, confirm_url, deny_url)

    subject = f"[Log+] {notif.title}"
    msg = EmailMultiAlternatives(
        subject=subject,
        body=text_body,
        from_email=getattr(settings, "DEFAULT_FROM_EMAIL", "noreply@logplus.ci"),
        to=[user.email],
    )
    msg.attach_alternative(html_body, "text/html")
    try:
        msg.send(fail_silently=False)
    except Exception as exc:
        logger.warning("Email send failed for %s: %s", user.email, exc)


def _render_html_email(user, notif, md, device_line, geo_line, confirm_url, deny_url) -> str:
    color = {"info": "#3B82F6", "warning": "#F59E0B", "critical": "#EF4444"}.get(notif.level, "#3B82F6")
    buttons_html = ""
    if confirm_url:
        buttons_html = f"""
        <div style="margin:24px 0;text-align:center;">
          <a href="{confirm_url}" style="background:#06D6A0;color:#fff;text-decoration:none;padding:11px 22px;border-radius:8px;font-weight:600;display:inline-block;margin-right:8px;">✓ C'est bien moi</a>
          <a href="{deny_url}" style="background:#EF4444;color:#fff;text-decoration:none;padding:11px 22px;border-radius:8px;font-weight:600;display:inline-block;">✗ Ce n'est pas moi</a>
        </div>
        """
    return f"""<!doctype html><html><body style="font-family:-apple-system,Segoe UI,Roboto,sans-serif;background:#0B1020;color:#E5E9F2;padding:24px;">
      <div style="max-width:560px;margin:auto;background:#111A30;border:1px solid #1E2A47;border-radius:14px;padding:28px;">
        <div style="display:flex;align-items:center;gap:10px;margin-bottom:8px;">
          <span style="display:inline-block;width:10px;height:10px;border-radius:50%;background:{color};"></span>
          <span style="font-size:11px;letter-spacing:0.08em;color:#8B9EC7;text-transform:uppercase;">Log+ — {notif.get_level_display()}</span>
        </div>
        <h1 style="font-size:20px;margin:6px 0 14px 0;color:#fff;">{notif.title}</h1>
        <p style="color:#B5C0D9;line-height:1.55;font-size:14px;">{notif.body}</p>
        <table style="margin-top:18px;font-size:13px;color:#B5C0D9;border-collapse:collapse;width:100%;">
          <tr><td style="padding:6px 0;color:#8B9EC7;width:130px;">Appareil</td><td>{device_line or '—'}</td></tr>
          <tr><td style="padding:6px 0;color:#8B9EC7;">Adresse IP</td><td><code>{md.get('ip_address') or '—'}</code></td></tr>
          <tr><td style="padding:6px 0;color:#8B9EC7;">Localisation</td><td>{geo_line or '—'}</td></tr>
          <tr><td style="padding:6px 0;color:#8B9EC7;">Service lié</td><td>{md.get('provider') or '—'} <span style="color:#6B7BA0;">({md.get('provider_email') or ''})</span></td></tr>
          <tr><td style="padding:6px 0;color:#8B9EC7;">Survenu</td><td>{md.get('occurred_at') or notif.created_at.isoformat()}</td></tr>
        </table>
        {buttons_html}
        <p style="font-size:11.5px;color:#6B7BA0;margin-top:24px;line-height:1.5;">
          Cet email vous est envoyé car vous avez lié votre compte <strong>{md.get('provider') or 'tiers'}</strong>
          à votre compte Log+. Vous pouvez gérer ces alertes dans Paramètres → Comptes liés.
        </p>
      </div>
    </body></html>"""


# ─────────────────────────────────────────────────────────────────────────────
# Public API
# ─────────────────────────────────────────────────────────────────────────────


def notify(
    user,
    *,
    kind: str,
    title: str,
    body: str = "",
    level: str = "info",
    linked_account: Optional[LinkedAccount] = None,
    event: Optional[ProviderLoginEvent] = None,
    metadata: Optional[dict] = None,
    create_confirmation: bool = False,
    send_email: bool = True,
) -> SecurityNotification:
    """Crée + dispatch une notification de sécurité multi-canal."""
    md = dict(metadata or {})
    if linked_account:
        md.setdefault("provider", linked_account.provider)
        md.setdefault("provider_email", linked_account.provider_email)
    if event:
        md.setdefault("ip_address", event.ip_address)
        md.setdefault("browser", event.browser)
        md.setdefault("os", event.os)
        md.setdefault("device_type", event.device_type)
        md.setdefault("geo_city", event.geo_city)
        md.setdefault("geo_country", event.geo_country)
        md.setdefault("occurred_at", event.occurred_at.isoformat())

    confirmation = None
    if create_confirmation:
        confirmation = LoginConfirmation.objects.create(
            user=user,
            linked_account=linked_account,
            event=event,
            ip_address=event.ip_address if event else None,
            browser=event.browser if event else "",
            os=event.os if event else "",
            device_type=event.device_type if event else "",
            geo_city=event.geo_city if event else "",
            geo_country=event.geo_country if event else "",
            expires_at=timezone.now() + timedelta(seconds=CONFIRM_TOKEN_MAX_AGE),
        )

    notif = SecurityNotification.objects.create(
        user=user, kind=kind, level=level, title=title, body=body,
        linked_account=linked_account, confirmation=confirmation, metadata=md,
    )

    payload = {
        "id": str(notif.id),
        "kind": notif.kind,
        "level": notif.level,
        "title": notif.title,
        "body": notif.body,
        "metadata": md,
        "confirmation_id": str(confirmation.id) if confirmation else None,
        "created_at": notif.created_at.isoformat(),
    }
    _push_websocket(user.id, payload)

    if send_email:
        _send_email(notif, confirmation)

    return notif
