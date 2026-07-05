"""
Enrichissement d'IP SANS clé API — garantit que le Threat Intel renvoie
toujours des données utiles, même quand AbuseIPDB / VirusTotal ne sont pas
configurés.

Deux sources :
  1. Géolocalisation & réseau via ip-api.com (gratuit, sans clé, 45 req/min) :
     pays, ville, FAI, ASN, et surtout les drapeaux proxy / hosting / mobile
     (une IP d'hébergeur ou de proxy est intrinsèquement plus suspecte).
  2. Empreinte interne SIEM : ce que NOTRE plateforme sait déjà de cette IP
     (échecs de connexion, alertes déclenchées, utilisateurs ciblés…). C'est
     la source la plus fiable pour une IP qui nous a déjà attaqués.
"""
import ipaddress
import logging

import httpx

logger = logging.getLogger(__name__)

IPAPI_URL = "http://ip-api.com/json/{ip}"
IPAPI_FIELDS = (
    "status,message,country,countryCode,regionName,city,isp,org,as,asname,"
    "reverse,proxy,hosting,mobile,query"
)


def _is_private(ip: str) -> bool:
    try:
        return ipaddress.ip_address(ip).is_private
    except ValueError:
        return False


def geo_lookup(ip: str) -> dict:
    """Géolocalisation + réseau via ip-api.com. Retourne {} si indisponible."""
    if not ip or _is_private(ip):
        return {}
    try:
        with httpx.Client(timeout=8.0) as client:
            resp = client.get(IPAPI_URL.format(ip=ip), params={"fields": IPAPI_FIELDS})
            resp.raise_for_status()
            data = resp.json()
            if data.get("status") != "success":
                return {}
            return data
    except (httpx.HTTPError, ValueError) as exc:
        logger.warning("ip-api geo lookup failed for %s: %s", ip, exc)
        return {}


def internal_reputation(ip: str) -> dict:
    """
    Réputation interne : agrège ce que le SIEM a observé pour cette IP.
    C'est la source clé pour repérer un attaquant récurrent de VOTRE infra.
    """
    from django.db.models import Count, Q

    from apps.alerts.models import Alert
    from apps.logs.models import NormalizedLog

    logs = NormalizedLog.objects.filter(source_ip=ip)
    total = logs.count()
    if total == 0:
        # IP jamais vue en interne — on le dit explicitement (pas "pas de données")
        return {"seen": False}

    failures = logs.filter(action="login_failure").count()
    successes = logs.filter(action="login_success").count()
    targeted_users = list(
        logs.exclude(user_email__isnull=True)
        .values("user_email")
        .annotate(n=Count("id"))
        .order_by("-n")[:8]
    )
    actions = list(
        logs.values("action").annotate(n=Count("id")).order_by("-n")[:6]
    )
    first_seen = logs.order_by("event_time").values_list("event_time", flat=True).first()
    last_seen = logs.order_by("-event_time").values_list("event_time", flat=True).first()

    # Alertes qui référencent cette IP via leurs logs sources
    alert_qs = Alert.objects.filter(source_logs__source_ip=ip).distinct()
    alert_count = alert_qs.count()
    alert_severities = list(
        alert_qs.values("severity").annotate(n=Count("id")).order_by("-n")
    )

    return {
        "seen": True,
        "total_events": total,
        "login_failures": failures,
        "login_successes": successes,
        "distinct_users_targeted": len(targeted_users),
        "targeted_users": [u["user_email"] for u in targeted_users],
        "top_actions": [{"action": a["action"], "count": a["n"]} for a in actions],
        "alert_count": alert_count,
        "alert_severities": {s["severity"]: s["n"] for s in alert_severities},
        "first_seen": first_seen.isoformat() if first_seen else None,
        "last_seen": last_seen.isoformat() if last_seen else None,
    }
