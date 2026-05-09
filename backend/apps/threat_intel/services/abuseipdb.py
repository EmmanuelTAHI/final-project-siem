"""
Client AbuseIPDB — vérifie la réputation d'une adresse IP.
https://docs.abuseipdb.com/#check-endpoint
"""
import logging

import httpx
from django.conf import settings

logger = logging.getLogger(__name__)

ABUSEIPDB_BASE = "https://api.abuseipdb.com/api/v2"


def check_ip(ip_address: str, max_age_in_days: int = 90) -> dict:
    """
    Vérifie la réputation d'une IP via AbuseIPDB.
    Retourne un dict avec: abuse_confidence_score, total_reports, is_public, country_code, ...
    """
    api_key = getattr(settings, "ABUSEIPDB_API_KEY", "")
    if not api_key:
        logger.debug("ABUSEIPDB_API_KEY non configurée — enrichissement ignoré")
        return {}

    try:
        with httpx.Client(timeout=10.0) as client:
            resp = client.get(
                f"{ABUSEIPDB_BASE}/check",
                params={"ipAddress": ip_address, "maxAgeInDays": max_age_in_days, "verbose": True},
                headers={"Key": api_key, "Accept": "application/json"},
            )
            resp.raise_for_status()
            return resp.json().get("data", {})
    except httpx.HTTPError as exc:
        logger.warning("AbuseIPDB check failed for %s: %s", ip_address, exc)
        return {}


def bulk_check_ips(ip_list: list[str]) -> dict[str, dict]:
    """Vérifie plusieurs IPs, retourne un dict ip→résultat."""
    results = {}
    for ip in set(ip_list):
        if ip and ip not in ("127.0.0.1", "::1", "0.0.0.0"):
            results[ip] = check_ip(ip)
    return results
