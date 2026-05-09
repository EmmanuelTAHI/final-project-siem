"""
Polling périodique des événements de sécurité chez Google / Microsoft / GitHub
pour les LinkedAccount actifs, normalisation, détection et notification.

Détections :
- new_device       : User-Agent (browser+OS+device_type) jamais vu pour ce LinkedAccount.
- new_location     : pays différent des 30 derniers jours.
- brute_force      : ≥ 5 échecs de connexion en 10 min.

À chaque détection on appelle notification_service.notify() qui s'occupe de
persister + push WS + email + (optionnel) ticket de confirmation signé.
"""
import logging
from datetime import timedelta
from typing import Iterable

import httpx
from django.utils import timezone

from ..models import LinkedAccount, ProviderLoginEvent
from .link_oauth_service import link_oauth_service
from .notification_service import notify

logger = logging.getLogger(__name__)

BRUTE_FORCE_THRESHOLD = 5
BRUTE_FORCE_WINDOW = timedelta(minutes=10)
KNOWN_LOCATION_LOOKBACK = timedelta(days=30)


# ─────────────────────────────────────────────────────────────────────────────
# User-Agent / Geo helpers (légers — sans dépendance externe pour l'instant)
# ─────────────────────────────────────────────────────────────────────────────


def parse_user_agent(ua: str) -> dict:
    if not ua:
        return {"browser": "", "os": "", "device_type": ""}
    s = ua.lower()
    browser = "Inconnu"
    if "edg" in s: browser = "Edge"
    elif "chrome" in s and "chromium" not in s: browser = "Chrome"
    elif "firefox" in s: browser = "Firefox"
    elif "safari" in s and "chrome" not in s: browser = "Safari"
    elif "opera" in s or "opr/" in s: browser = "Opera"
    elif "curl" in s or "wget" in s or "python" in s or "go-http" in s: browser = "Bot/Script"

    os_name = "Inconnu"
    if "windows" in s: os_name = "Windows"
    elif "mac os" in s or "darwin" in s: os_name = "macOS"
    elif "android" in s: os_name = "Android"
    elif "iphone" in s or "ios " in s or "ipad" in s: os_name = "iOS"
    elif "linux" in s: os_name = "Linux"

    device_type = "desktop"
    if "mobile" in s or "android" in s: device_type = "mobile"
    elif "ipad" in s or "tablet" in s: device_type = "tablet"
    elif browser == "Bot/Script": device_type = "server"

    return {"browser": browser, "os": os_name, "device_type": device_type}


def fingerprint_device(parsed_ua: dict) -> str:
    return f"{parsed_ua.get('browser')}|{parsed_ua.get('os')}|{parsed_ua.get('device_type')}"


# ─────────────────────────────────────────────────────────────────────────────
# Provider fetchers
# ─────────────────────────────────────────────────────────────────────────────


def _fetch_google_events(account: LinkedAccount, access_token: str) -> Iterable[dict]:
    """
    Reports API — applicationName=login.
    Retourne des événements normalisés (dict) prêts pour _ingest_event.
    """
    headers = {"Authorization": f"Bearer {access_token}"}
    params = {"maxResults": 50}
    url = "https://admin.googleapis.com/admin/reports/v1/activity/users/all/applications/login"
    try:
        with httpx.Client(timeout=20) as client:
            r = client.get(url, headers=headers, params=params)
        if r.status_code != 200:
            logger.info("Google reports HTTP %d for %s", r.status_code, account.provider_email)
            return []
        items = r.json().get("items", [])
    except Exception as exc:
        logger.warning("Google fetch failed: %s", exc)
        return []

    out = []
    for it in items:
        for ev in it.get("events", []):
            name = (ev.get("name") or "").lower()
            etype = "login_success" if name in ("login_success", "logout") else (
                "login_failure" if "failure" in name else "unknown"
            )
            params_map = {p.get("name"): p.get("value") for p in ev.get("parameters", [])}
            out.append({
                "provider_event_id": it.get("id", {}).get("uniqueQualifier") or it.get("id", {}).get("time", "") + name,
                "occurred_at": it.get("id", {}).get("time"),
                "event_type": etype,
                "ip_address": it.get("ipAddress"),
                "user_agent": "",
                "raw": it,
                "geo_country": params_map.get("login_challenge_method") and "" or "",
            })
    return out


def _fetch_microsoft_events(account: LinkedAccount, access_token: str) -> Iterable[dict]:
    """Microsoft Graph /auditLogs/signIns filtré sur l'utilisateur."""
    headers = {"Authorization": f"Bearer {access_token}"}
    url = (
        "https://graph.microsoft.com/v1.0/auditLogs/signIns"
        f"?$filter=userId eq '{account.provider_user_id}'&$top=50"
    )
    try:
        with httpx.Client(timeout=20) as client:
            r = client.get(url, headers=headers)
        if r.status_code != 200:
            logger.info("MS signIns HTTP %d", r.status_code)
            return []
        items = r.json().get("value", [])
    except Exception as exc:
        logger.warning("MS fetch failed: %s", exc)
        return []

    out = []
    for s in items:
        status_code = (s.get("status") or {}).get("errorCode", 0)
        etype = "login_success" if status_code == 0 else "login_failure"
        device = s.get("deviceDetail") or {}
        location = s.get("location") or {}
        out.append({
            "provider_event_id": s.get("id"),
            "occurred_at": s.get("createdDateTime"),
            "event_type": etype,
            "ip_address": s.get("ipAddress"),
            "user_agent": (s.get("clientAppUsed") or "") + " " + (device.get("operatingSystem") or "") + " " + (device.get("browser") or ""),
            "raw": s,
            "geo_country": location.get("countryOrRegion", "")[:2],
            "geo_city": location.get("city", ""),
        })
    return out


def _fetch_github_events(account: LinkedAccount, access_token: str) -> Iterable[dict]:
    """
    GitHub n'expose pas les login failures côté user. On utilise /user/events pour les
    événements visibles + /user pour vérifier le device de la session courante.
    """
    headers = {"Authorization": f"Bearer {access_token}", "Accept": "application/vnd.github+json"}
    url = f"https://api.github.com/users/{account.provider_display_name or 'me'}/events?per_page=50"
    try:
        with httpx.Client(timeout=20) as client:
            r = client.get(url, headers=headers)
        if r.status_code != 200:
            logger.info("GitHub events HTTP %d", r.status_code)
            return []
        items = r.json()
    except Exception as exc:
        logger.warning("GitHub fetch failed: %s", exc)
        return []

    out = []
    for ev in items:
        if ev.get("type") not in ("PublicEvent", "WatchEvent", "PushEvent", "CreateEvent"):
            continue
        out.append({
            "provider_event_id": ev.get("id"),
            "occurred_at": ev.get("created_at"),
            "event_type": "login_success",
            "ip_address": None,
            "user_agent": "",
            "raw": ev,
        })
    return out


PROVIDER_FETCHERS = {
    "google": _fetch_google_events,
    "microsoft": _fetch_microsoft_events,
    "github": _fetch_github_events,
}


# ─────────────────────────────────────────────────────────────────────────────
# Ingestion + détection
# ─────────────────────────────────────────────────────────────────────────────


def _parse_dt(value):
    if not value:
        return timezone.now()
    if hasattr(value, "isoformat"):
        return value
    try:
        from datetime import datetime
        v = value.replace("Z", "+00:00") if isinstance(value, str) else value
        return datetime.fromisoformat(v)
    except Exception:
        return timezone.now()


def _ingest_event(account: LinkedAccount, raw: dict) -> ProviderLoginEvent | None:
    """Crée un ProviderLoginEvent (idempotent via provider_event_id) et lance les détections."""
    pid = raw.get("provider_event_id") or ""
    if not pid:
        return None

    parsed_ua = parse_user_agent(raw.get("user_agent") or "")
    occurred = _parse_dt(raw.get("occurred_at"))

    event, created = ProviderLoginEvent.objects.get_or_create(
        linked_account=account,
        provider_event_id=pid,
        defaults={
            "event_type": raw.get("event_type", "unknown"),
            "occurred_at": occurred,
            "ip_address": raw.get("ip_address"),
            "user_agent": raw.get("user_agent", "")[:8000],
            "browser": parsed_ua["browser"],
            "os": parsed_ua["os"],
            "device_type": parsed_ua["device_type"],
            "geo_country": (raw.get("geo_country") or "")[:2],
            "geo_city": (raw.get("geo_city") or "")[:120],
            "raw": raw.get("raw") or {},
        },
    )
    if not created:
        return event

    # Détections (uniquement sur events frais)
    _run_detections(account, event)
    return event


def _run_detections(account: LinkedAccount, event: ProviderLoginEvent) -> None:
    user = account.user

    # --- 1) Brute force --------------------------------------------------------
    if event.event_type == "login_failure":
        recent_failures = ProviderLoginEvent.objects.filter(
            linked_account=account,
            event_type="login_failure",
            occurred_at__gte=event.occurred_at - BRUTE_FORCE_WINDOW,
            occurred_at__lte=event.occurred_at,
        ).count()
        if recent_failures >= BRUTE_FORCE_THRESHOLD:
            event.risk_score = max(event.risk_score, 90)
            event.save(update_fields=["risk_score"])
            account.status = "paused"
            account.save(update_fields=["status", "updated_at"])
            notify(
                user, kind="brute_force", level="critical",
                title=f"Tentative de brute-force sur votre compte {account.provider}",
                body=(
                    f"{recent_failures} échecs de connexion en moins de "
                    f"{int(BRUTE_FORCE_WINDOW.total_seconds() / 60)} minutes sur votre compte "
                    f"{account.provider} ({account.provider_email}). "
                    f"Le compte a été mis en pause par sécurité."
                ),
                linked_account=account, event=event,
                metadata={"failures": recent_failures, "ip_address": event.ip_address},
                create_confirmation=False, send_email=True,
            )
            return  # pas la peine de spammer new_device en plus

    if event.event_type != "login_success":
        return

    # --- 2) New device ---------------------------------------------------------
    fp = fingerprint_device({"browser": event.browser, "os": event.os, "device_type": event.device_type})
    known_device = ProviderLoginEvent.objects.filter(
        linked_account=account, event_type="login_success",
        browser=event.browser, os=event.os, device_type=event.device_type,
    ).exclude(pk=event.pk).exists()
    event.is_known_device = known_device

    # --- 3) New location -------------------------------------------------------
    known_location = (
        bool(event.geo_country)
        and ProviderLoginEvent.objects.filter(
            linked_account=account,
            event_type="login_success",
            geo_country=event.geo_country,
            occurred_at__gte=event.occurred_at - KNOWN_LOCATION_LOOKBACK,
        ).exclude(pk=event.pk).exists()
    )
    event.is_known_location = known_location
    event.save(update_fields=["is_known_device", "is_known_location"])

    if not known_device or not known_location:
        kind = "login_new_device" if not known_device else "login_new_location"
        event.risk_score = max(event.risk_score, 60 if not known_device else 40)
        event.save(update_fields=["risk_score"])
        title = (
            f"Nouvelle connexion sur votre compte {account.provider}"
            if not known_device
            else f"Nouvelle géolocalisation sur votre compte {account.provider}"
        )
        body = (
            f"Une connexion vient d'être détectée sur votre compte {account.provider} "
            f"({account.provider_email}). Si ce n'est pas vous, cliquez sur « Ce n'est pas moi » "
            f"pour révoquer immédiatement la session."
        )
        notify(
            user, kind=kind, level="warning",
            title=title, body=body,
            linked_account=account, event=event,
            metadata={"fingerprint": fp},
            create_confirmation=True, send_email=True,
        )


# ─────────────────────────────────────────────────────────────────────────────
# Public — appelé par Celery
# ─────────────────────────────────────────────────────────────────────────────


def poll_account(account: LinkedAccount) -> int:
    """Poll un LinkedAccount actif. Retourne le nombre de nouveaux events ingérés."""
    if account.status != "active":
        return 0
    fetcher = PROVIDER_FETCHERS.get(account.provider)
    if not fetcher:
        return 0

    try:
        token = link_oauth_service.get_access_token(account)
    except Exception as exc:
        logger.warning("Token unavailable for %s: %s", account, exc)
        account.status = "error"
        account.save(update_fields=["status", "updated_at"])
        return 0

    raw_events = list(fetcher(account, token))
    new_count = 0
    for raw in raw_events:
        ev = _ingest_event(account, raw)
        if ev and ev.received_at >= timezone.now() - timedelta(seconds=10):
            new_count += 1

    account.last_polled_at = timezone.now()
    account.save(update_fields=["last_polled_at", "updated_at"])
    return new_count


def poll_all_active_accounts() -> dict:
    accounts = LinkedAccount.objects.filter(status="active")
    total_events = 0
    polled = 0
    for acc in accounts:
        try:
            n = poll_account(acc)
            total_events += n
            polled += 1
        except Exception:
            logger.exception("poll_account failed for %s", acc)
    return {"polled": polled, "new_events": total_events}
