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
            resp.raise_for_status()
            data = resp.json()
            if str(data.get("status")) not in ("200", "success", "True"):
                # CriminalIP renvoie parfois status=200 en int, parfois un message
                if data.get("status") not in (200,):
                    logger.debug("CriminalIP status inattendu pour %s: %s", ip_address, data.get("status"))
            return data
    except httpx.HTTPError as exc:
        logger.warning("CriminalIP check failed for %s: %s", ip_address, exc)
        return {}


def summarize(data: dict) -> dict:
    """Extrait les champs clés d'une réponse CriminalIP summary."""
    if not data:
        return {}
    issues = data.get("issues", {}) or {}
    score = data.get("score", {}) or {}
    return {
        "inbound_score": score.get("inbound"),
        "outbound_score": score.get("outbound"),
        "is_vpn": issues.get("is_vpn"),
        "is_proxy": issues.get("is_proxy"),
        "is_tor": issues.get("is_tor"),
        "is_hosting": issues.get("is_cloud") or issues.get("is_hosting"),
        "is_scanner": issues.get("is_scanner"),
        "is_malicious": issues.get("is_malicious"),
        "is_darkweb": issues.get("is_darkweb"),
        "country": (data.get("country") or {}).get("name") if isinstance(data.get("country"), dict) else data.get("country"),
        "open_ports": data.get("current_opened_port", {}).get("count")
        if isinstance(data.get("current_opened_port"), dict)
        else None,
    }
