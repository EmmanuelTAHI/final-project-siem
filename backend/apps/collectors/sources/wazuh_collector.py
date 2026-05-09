"""
Collecteur Wazuh via Wazuh REST API.
Endpoint : GET https://{wazuh_host}:55000/alerts
"""
import logging
import time
from typing import Generator

import httpx
from django.conf import settings

from .base_collector import BaseCollector

logger = logging.getLogger(__name__)


class WazuhCollector(BaseCollector):
    """
    Collecteur des alertes Wazuh via son API REST.
    Authentification par credentials (Basic Auth ou JWT Wazuh).
    """

    def _get_wazuh_token(self) -> str:
        """
        Obtient un token JWT Wazuh via Basic Auth.
        """
        credentials = self.connector.get_credentials()
        wazuh_url = credentials.get("api_url", settings.WAZUH_API_URL)
        username = credentials.get("username", settings.WAZUH_USERNAME)
        password = credentials.get("password", settings.WAZUH_PASSWORD)
        verify_ssl = credentials.get("verify_ssl", settings.WAZUH_VERIFY_SSL)

        auth_url = f"{wazuh_url}/security/user/authenticate"
        with httpx.Client(timeout=15, verify=verify_ssl) as client:
            response = client.get(auth_url, auth=(username, password))

        if response.status_code != 200:
            raise ValueError(
                f"Authentification Wazuh échouée : HTTP {response.status_code} — {response.text[:300]}"
            )
        return response.json()["data"]["token"]

    def fetch_logs(self) -> Generator[dict, None, None]:
        """
        Récupère les alertes Wazuh depuis la dernière collecte.
        """
        credentials = self.connector.get_credentials()
        wazuh_url = credentials.get("api_url", settings.WAZUH_API_URL)
        verify_ssl = credentials.get("verify_ssl", settings.WAZUH_VERIFY_SSL)

        token = self._get_wazuh_token()
        headers = {
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json",
        }

        import django.utils.timezone as timezone
        last_collected = self.connector.last_collected_at
        if last_collected:
            from_timestamp = int(last_collected.timestamp() * 1000)
        else:
            from datetime import timedelta
            start = timezone.now() - timedelta(hours=24)
            from_timestamp = int(start.timestamp() * 1000)

        offset = 0
        limit = 500

        with httpx.Client(timeout=60, verify=verify_ssl) as client:
            while True:
                params = {
                    "offset": offset,
                    "limit": limit,
                    "sort": "+timestamp",
                    "q": f"timestamp>{from_timestamp}",
                }
                url = f"{wazuh_url}/alerts"
                response = client.get(url, headers=headers, params=params)

                if response.status_code == 401:
                    logger.warning("Token Wazuh expiré, re-authentification...")
                    token = self._get_wazuh_token()
                    headers["Authorization"] = f"Bearer {token}"
                    response = client.get(url, headers=headers, params=params)

                response.raise_for_status()
                data = response.json()

                alerts = data.get("data", {}).get("affected_items", [])
                for alert in alerts:
                    alert["_source"] = "wazuh"
                    yield alert

                total = data.get("data", {}).get("total_affected_items", 0)
                offset += limit
                if offset >= total or not alerts:
                    break

                logger.debug("Wazuh : collecte %d/%d alertes", min(offset, total), total)

    def test_connection(self) -> dict:
        """Teste la connexion à l'API Wazuh."""
        start_time = time.time()
        try:
            self._get_wazuh_token()
            latency_ms = (time.time() - start_time) * 1000
            return {
                "reachable": True,
                "latency_ms": round(latency_ms, 2),
                "message": "Connexion Wazuh API réussie.",
            }
        except Exception as exc:
            latency_ms = (time.time() - start_time) * 1000
            return {
                "reachable": False,
                "latency_ms": round(latency_ms, 2),
                "message": str(exc),
            }
