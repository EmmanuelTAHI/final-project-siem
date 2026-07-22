"""
Flux de threat intel COLLABORATIFS et gratuits (sans clé API), alimentés par
la communauté abuse.ch — reproduit l'avantage "blocklist partagée entre tous
les utilisateurs" mis en avant par CrowdSec, directement intégré au SIEM.
"""
import csv
import io
import ipaddress
import logging

import httpx

logger = logging.getLogger(__name__)

URLHAUS_RECENT_CSV = "https://urlhaus.abuse.ch/downloads/csv_recent/"
FEODOTRACKER_IPBLOCKLIST_JSON = "https://feodotracker.abuse.ch/downloads/ipblocklist.json"


def is_ip(value: str) -> bool:
    try:
        ipaddress.ip_address(value)
        return True
    except ValueError:
        return False


def fetch_urlhaus_recent(limit: int = 500) -> list[dict]:
    """
    URLhaus : URLs de distribution de malware signalées par la communauté
    dans les dernières 24-48h. Retourne des dicts avec au moins "host" et
    "url"/"threat".
    """
    try:
        with httpx.Client(timeout=30.0) as client:
            resp = client.get(URLHAUS_RECENT_CSV)
            resp.raise_for_status()
            text = resp.text
    except httpx.HTTPError as exc:
        logger.warning("URLhaus fetch failed: %s", exc)
        return []

    lines = [line for line in text.splitlines() if line and not line.startswith("#")]
    reader = csv.reader(lines)
    results = []
    for row in reader:
        if len(row) < 6:
            continue
        # id,dateadded,url,url_status,last_online,threat,tags,urlhaus_link,reporter
        url = row[2].strip('"')
        threat = row[5].strip('"') if len(row) > 5 else "malware_download"
        try:
            from urllib.parse import urlparse
            host = urlparse(url).hostname
        except Exception:
            host = None
        if host:
            results.append({"host": host, "url": url, "threat": threat})
        if len(results) >= limit:
            break
    return results


def fetch_feodo_ipblocklist(limit: int = 1000) -> list[str]:
    """
    Feodo Tracker : IPs de serveurs de commande-et-contrôle (C2) de botnets
    bancaires connus (Dridex, Emotet, TrickBot, QakBot...), mises à jour en
    continu par la communauté.
    """
    try:
        with httpx.Client(timeout=30.0) as client:
            resp = client.get(FEODOTRACKER_IPBLOCKLIST_JSON)
            resp.raise_for_status()
            data = resp.json()
    except httpx.HTTPError as exc:
        logger.warning("Feodo Tracker fetch failed: %s", exc)
        return []

    ips = [entry.get("ip_address") for entry in data if entry.get("ip_address")]
    return ips[:limit]
