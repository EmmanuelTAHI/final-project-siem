"""
Client CriminalIP — réputation et exposition d'une IP.
https://www.criminalip.io/developer/api/get-ip-data
"""
import logging

import httpx
from django.conf import settings

logger = logging.getLogger(__name__)

CRIMINALIP_BASE = "https://api.criminalip.io/v1"


def check_ip(ip_address: str) -> dict:
    """
    Interroge CriminalIP (endpoint summary) : score inbound/outbound, drapeaux
    (proxy, vpn, tor, hosting, scanner, malicious), pays, ports ouverts.
    Retourne {} si clé absente ou erreur.
    """
    api_key = getattr(settings, "CRIMINALIP_API_KEY", "")
    if not api_key:
        logger.debug("CRIMINALIP_API_KEY non configurée — ignoré")
        return {}

    try:
        with httpx.Client(timeout=12.0) as client:
            resp = client.get(
                f"{CRIMINALIP_BASE}/asset/ip/report/summary",
                params={"ip": ip_address},
                headers={"x-api-key": api_key},
            )
            body = resp.json() if resp.content else {}
            # CriminalIP renvoie 200 HTTP mais un status applicatif dans le corps.
            app_status = body.get("status")
            if resp.status_code >= 400 or app_status in (401, 403, 429):
                msg = body.get("message") or f"HTTP {resp.status_code}"
                return {"_error": str(msg), "_status": app_status or resp.status_code}
            return body
    except httpx.HTTPError as exc:
        logger.warning("CriminalIP check failed for %s: %s", ip_address, exc)
        return {}


def summarize(data: dict) -> dict:
    """Extrait les champs clés d'une réponse CriminalIP summary."""
    if not data:
        return {}
    if data.get("_error"):
        return {"error": data["_error"], "status": data.get("_status")}

    # Les champs utiles sont sous `data` (le corps enveloppe data/status/message).
    d = data.get("data") if isinstance(data.get("data"), dict) else data
    issues = d.get("issues", {}) or {}
    score = d.get("score", {}) or {}
    # score.inbound/outbound sont des niveaux texte : Low / Moderate / Dangerous / Critical
    LEVELS = {"low": 10, "moderate": 45, "dangerous": 75, "critical": 95, "safe": 0}

    def lvl(v):
        if isinstance(v, (int, float)):
            return v
        return LEVELS.get(str(v).lower(), None)

    port_info = d.get("current_opened_port")
    open_ports = port_info.get("count") if isinstance(port_info, dict) else None
    country = d.get("country")
    if isinstance(country, dict):
        country = country.get("name")

    return {
        "inbound_score": lvl(score.get("inbound")),
        "outbound_score": lvl(score.get("outbound")),
        "inbound_level": score.get("inbound"),
        "is_vpn": issues.get("is_vpn"),
        "is_proxy": issues.get("is_proxy"),
        "is_tor": issues.get("is_tor"),
        "is_hosting": issues.get("is_cloud") or issues.get("is_hosting"),
        "is_scanner": issues.get("is_scanner") or issues.get("is_snort"),
        "is_malicious": issues.get("is_malicious"),
        "is_darkweb": issues.get("is_darkweb"),
        "country": country,
        "open_ports": open_ports,
    }
