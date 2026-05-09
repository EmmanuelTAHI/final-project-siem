"""
Client VirusTotal v3 — analyse des IPs, domaines et hashes.
https://developers.virustotal.com/reference/overview
"""
import logging

import httpx
from django.conf import settings

logger = logging.getLogger(__name__)

VT_BASE = "https://www.virustotal.com/api/v3"


def _headers() -> dict:
    return {"x-apikey": getattr(settings, "VIRUSTOTAL_API_KEY", ""), "Accept": "application/json"}


def _vt_get(endpoint: str) -> dict:
    api_key = getattr(settings, "VIRUSTOTAL_API_KEY", "")
    if not api_key:
        logger.debug("VIRUSTOTAL_API_KEY non configurée — enrichissement ignoré")
        return {}
    try:
        with httpx.Client(timeout=15.0) as client:
            resp = client.get(f"{VT_BASE}/{endpoint}", headers=_headers())
            if resp.status_code == 404:
                return {}
            resp.raise_for_status()
            return resp.json().get("data", {})
    except httpx.HTTPError as exc:
        logger.warning("VirusTotal request failed (%s): %s", endpoint, exc)
        return {}


def analyze_ip(ip_address: str) -> dict:
    """Analyse d'une IP : retourne last_analysis_stats, reputation, country, ..."""
    return _vt_get(f"ip_addresses/{ip_address}")


def analyze_domain(domain: str) -> dict:
    """Analyse d'un domaine."""
    return _vt_get(f"domains/{domain}")


def analyze_hash(file_hash: str) -> dict:
    """Analyse d'un hash de fichier (MD5, SHA1, SHA256)."""
    return _vt_get(f"files/{file_hash}")


def get_malicious_score(vt_data: dict) -> float:
    """Extrait un score de 0 à 100 depuis les stats VirusTotal."""
    stats = vt_data.get("attributes", {}).get("last_analysis_stats", {})
    malicious = stats.get("malicious", 0)
    total = sum(stats.values()) if stats else 0
    if total == 0:
        return 0.0
    return round((malicious / total) * 100, 2)
