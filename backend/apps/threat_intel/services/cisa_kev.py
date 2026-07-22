"""
Client CISA KEV (Known Exploited Vulnerabilities) — catalogue public des
vulnérabilités EXPLOITÉES ACTIVEMENT dans la nature, maintenu par la CISA
(agence de cybersécurité américaine). Gratuit, sans clé API.
https://www.cisa.gov/known-exploited-vulnerabilities-catalog
"""
import logging

import httpx

logger = logging.getLogger(__name__)

CISA_KEV_FEED_URL = (
    "https://www.cisa.gov/sites/default/files/feeds/known_exploited_vulnerabilities.json"
)


def fetch_kev_catalog() -> list[dict]:
    """
    Récupère le catalogue complet CISA KEV.
    Retourne une liste de dicts avec: cveID, vendorProject, product,
    shortDescription, dateAdded, dueDate, requiredAction,
    knownRansomwareCampaignUse.
    """
    try:
        with httpx.Client(timeout=30.0) as client:
            resp = client.get(CISA_KEV_FEED_URL)
            resp.raise_for_status()
            data = resp.json()
            return data.get("vulnerabilities", [])
    except httpx.HTTPError as exc:
        logger.warning("CISA KEV fetch failed: %s", exc)
        return []
