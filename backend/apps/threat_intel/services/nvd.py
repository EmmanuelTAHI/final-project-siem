"""
Client NVD (National Vulnerability Database) — API CVE 2.0 du NIST.
Fonctionne sans clé (5 requêtes/30s), une clé NVD_API_KEY (gratuite,
https://nvd.nist.gov/developers/request-an-api-key) relève la limite à
50 requêtes/30s.
"""
import logging

import httpx
from django.conf import settings

logger = logging.getLogger(__name__)

NVD_BASE = "https://services.nvd.nist.gov/rest/json/cves/2.0"


def fetch_recent_cves(days: int = 1, results_per_page: int = 200) -> list[dict]:
    """
    Récupère les CVE publiées/modifiées dans les `days` derniers jours.
    Retourne la liste brute des items NVD (chacun avec une clé "cve").
    """
    from datetime import datetime, timedelta, timezone as dt_timezone

    api_key = getattr(settings, "NVD_API_KEY", "")
    headers = {"apiKey": api_key} if api_key else {}

    end = datetime.now(dt_timezone.utc)
    start = end - timedelta(days=days)

    params = {
        "lastModStartDate": start.strftime("%Y-%m-%dT%H:%M:%S.000%z"),
        "lastModEndDate": end.strftime("%Y-%m-%dT%H:%M:%S.000%z"),
        "resultsPerPage": results_per_page,
    }

    try:
        with httpx.Client(timeout=30.0) as client:
            resp = client.get(NVD_BASE, params=params, headers=headers)
            resp.raise_for_status()
            return resp.json().get("vulnerabilities", [])
    except httpx.HTTPError as exc:
        logger.warning("NVD fetch failed: %s", exc)
        return []


def extract_cvss_score(cve: dict) -> float | None:
    """Extrait le meilleur score CVSS disponible (v3.1 > v3.0 > v2)."""
    metrics = cve.get("metrics", {})
    for key in ("cvssMetricV31", "cvssMetricV30", "cvssMetricV2"):
        entries = metrics.get(key) or []
        if entries:
            try:
                return float(entries[0]["cvssData"]["baseScore"])
            except (KeyError, TypeError, ValueError):
                continue
    return None


def score_to_severity(score: float | None) -> str:
    if score is None:
        return ""
    if score >= 9.0:
        return "critical"
    if score >= 7.0:
        return "high"
    if score >= 4.0:
        return "medium"
    return "low"


def extract_vendor_product(cve: dict) -> tuple[str, str]:
    """Best-effort : extrait le premier vendor/product cité par NVD (configurations CPE)."""
    for config in cve.get("configurations", []):
        for node in config.get("nodes", []):
            for cpe_match in node.get("cpeMatch", []):
                criteria = cpe_match.get("criteria", "")
                # cpe:2.3:a:vendor:product:version:...
                parts = criteria.split(":")
                if len(parts) >= 5:
                    return parts[3], parts[4]
    return "", ""
