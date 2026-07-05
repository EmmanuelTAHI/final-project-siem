"""
Client Shodan — surface d'exposition d'une IP (ports ouverts, services, CVE).
https://developer.shodan.io/api
"""
import logging

import httpx
from django.conf import settings

logger = logging.getLogger(__name__)

SHODAN_BASE = "https://api.shodan.io"


def host_info(ip_address: str) -> dict:
    """
    Renvoie les informations d'hôte Shodan : ports ouverts, produits/services,
    vulnérabilités (CVE), organisation, OS. Retourne {} si clé absente ou
    IP inconnue de Shodan (404).
    """
    api_key = getattr(settings, "SHODAN_API_KEY", "")
    if not api_key:
        logger.debug("SHODAN_API_KEY non configurée — ignoré")
        return {}

    try:
        with httpx.Client(timeout=12.0) as client:
            resp = client.get(
                f"{SHODAN_BASE}/shodan/host/{ip_address}",
                params={"key": api_key, "minify": "true"},
            )
            if resp.status_code == 404:
                return {"_not_found": True}
            resp.raise_for_status()
            return resp.json()
    except httpx.HTTPError as exc:
        logger.warning("Shodan host lookup failed for %s: %s", ip_address, exc)
        return {}


def summarize(data: dict) -> dict:
    """Extrait les champs clés d'une réponse Shodan host."""
    if not data or data.get("_not_found"):
        return {"not_found": bool(data.get("_not_found"))} if data else {}
    return {
        "ports": data.get("ports", []),
        "vulns": list(data.get("vulns", []))[:20],
        "vuln_count": len(data.get("vulns", []) or []),
        "org": data.get("org"),
        "isp": data.get("isp"),
        "os": data.get("os"),
        "country": data.get("country_name"),
        "hostnames": data.get("hostnames", []),
        "tags": data.get("tags", []),
        "last_update": data.get("last_update"),
    }
