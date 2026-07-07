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
from datetime import datetime, timedelta
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
    from . import email_theme as t

    accent = t.LEVEL_COLORS.get(notif.level, t.PRIMARY)
    name = (user.first_name or user.email or "").strip()

    rows = [
        ("Appareil", device_line or "—"),
        ("Adresse IP", f"<code>{md.get('ip_address') or '—'}</code>"),
        ("Localisation", geo_line or "—"),
    ]
    if md.get("provider"):
        rows.append(("Service lié", f"{md.get('provider')} <span style=\"color:{t.MUTED};\">({md.get('provider_email') or ''})</span>"))

    occurred_raw = md.get("occurred_at")
    occurred_dt = notif.created_at
    if occurred_raw:
        try:
            occurred_dt = datetime.fromisoformat(occurred_raw)
        except (TypeError, ValueError):
            pass
    rows.append(("Survenu", occurred_dt.strftime("%d/%m/%Y à %H:%M:%S UTC")))

    buttons_html = ""
    if confirm_url:
        buttons_html = f"""
            <table cellpadding="0" cellspacing="0" border="0" align="center" style="margin:22px auto 4px;">
              <tr>
                <td style="padding-right:8px;">
                  <table cellpadding="0" cellspacing="0" border="0"><tr>
                    <td style="border-radius:10px;background:{t.SECONDARY};">
                      <a href="{confirm_url}" style="display:inline-block;padding:12px 22px;font-size:13.5px;font-weight:700;color:#fff;text-decoration:none;border-radius:10px;">&#10003; C'est bien moi</a>
                    </td>
                  </tr></table>
                </td>
                <td>
                  <table cellpadding="0" cellspacing="0" border="0"><tr>
                    <td style="border-radius:10px;background:{t.DANGER};">
                      <a href="{deny_url}" style="display:inline-block;padding:12px 22px;font-size:13.5px;font-weight:700;color:#fff;text-decoration:none;border-radius:10px;">&#10007; Ce n'est pas moi</a>
                    </td>
                  </tr></table>
                </td>
              </tr>
            </table>"""

    footer_extra = ""
    if md.get("provider"):
        footer_extra = (
            f'<p style="margin:0 0 12px;font-size:11.5px;color:{t.MUTED};line-height:1.6;">'
            f'Cet email vous est envoyé car vous avez lié votre compte <strong style="color:{t.TEXT_DIM};">{md.get("provider")}</strong> '
            "à votre compte Log+. Vous pouvez gérer ces alertes dans Paramètres → Comptes liés.</p>"
        )

    body = f"""
            <p style="margin:0 0 4px;font-size:14.5px;color:{t.TEXT};line-height:1.6;">{notif.body}</p>
            {t.metadata_table(rows)}
            {buttons_html}
    """

    warning = "" if confirm_url else (
        "Si vous ne reconnaissez pas cette activité, changez votre mot de passe et révoquez vos sessions actives sans délai."
        if notif.level == "critical" else ""
    )

    return t.render_email(
        preheader=notif.title,
        badge_label=notif.get_level_display(),
        badge_letter="!" if notif.level == "critical" else ("i" if notif.level == "info" else "⚠"),
        accent=accent,
        title=notif.title,
        subtitle_html=f"Bonjour <strong style=\"color:{t.TEXT};\">{name}</strong>,",
        body_html=body,
        warning_html=warning,
        footer_extra=footer_extra,
    )


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
