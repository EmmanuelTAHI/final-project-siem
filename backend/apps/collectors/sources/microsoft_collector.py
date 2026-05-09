"""
Collecteur Microsoft 365 via Microsoft Graph API.
Endpoint : GET https://graph.microsoft.com/v1.0/auditLogs/signIns
"""
import logging
import time
from typing import Generator

import httpx
import django.utils.timezone as timezone

from apps.authentication.services.token_service import token_service

from .base_collector import BaseCollector

logger = logging.getLogger(__name__)

GRAPH_BASE_URL = "https://graph.microsoft.com/v1.0"
SIGN_INS_FIELDS = (
    "id,createdDateTime,userDisplayName,userPrincipalName,"
    "ipAddress,location,status,clientAppUsed,appDisplayName,"
    "conditionalAccessStatus,riskDetail,riskLevelAggregated"
)


class MicrosoftCollector(BaseCollector):
    """
    Collecteur des logs de connexion Microsoft 365.
    Utilise Microsoft Graph API avec pagination @odata.nextLink.
    """

    def fetch_logs(self) -> Generator[dict, None, None]:
        """
        Récupère les logs de connexion Microsoft 365 depuis la dernière collecte.
        Gère automatiquement la pagination @odata.nextLink.
        """
        access_token = token_service.get_valid_access_token(self.connector)

        last_collected = self.connector.last_collected_at
        if last_collected:
            filter_dt = last_collected.strftime("%Y-%m-%dT%H:%M:%SZ")
            filter_param = f"createdDateTime ge {filter_dt}"
        else:
            # Première collecte : 24 dernières heures
            from datetime import timedelta
            start = timezone.now() - timedelta(hours=24)
            filter_param = f"createdDateTime ge {start.strftime('%Y-%m-%dT%H:%M:%SZ')}"

        url = f"{GRAPH_BASE_URL}/auditLogs/signIns"
        params = {
            "$filter": filter_param,
            "$top": 999,
            "$select": SIGN_INS_FIELDS,
        }
        headers = {
            "Authorization": f"Bearer {access_token}",
            "Content-Type": "application/json",
            "ConsistencyLevel": "eventual",
        }

        page_count = 0
        with httpx.Client(timeout=60, follow_redirects=True) as client:
            while url:
                response = client.get(url, headers=headers, params=params if page_count == 0 else None)

                if response.status_code == 401:
                    # Token expiré → refresh et retry
                    logger.warning("Token Microsoft expiré, tentative de refresh...")
                    token_service.refresh_token(self.connector)
                    access_token = token_service.get_valid_access_token(self.connector)
                    headers["Authorization"] = f"Bearer {access_token}"
                    response = client.get(url, headers=headers, params=params if page_count == 0 else None)

                if response.status_code == 429:
                    retry_after = int(response.headers.get("Retry-After", 60))
                    logger.warning("Rate limit Microsoft Graph. Attente %ds...", retry_after)
                    time.sleep(retry_after)
                    continue

                response.raise_for_status()
                data = response.json()

                for log_entry in data.get("value", []):
                    yield self._enrich_log(log_entry)

                url = data.get("@odata.nextLink")
                page_count += 1
                logger.debug("Microsoft page %d collectée (%d logs)", page_count, len(data.get("value", [])))

    def _enrich_log(self, log_entry: dict) -> dict:
        """Ajoute des métadonnées internes au log brut."""
        log_entry["_source"] = "microsoft365"
        return log_entry

    def test_connection(self) -> dict:
        """Teste la connexion à Microsoft Graph API."""
        start_time = time.time()
        try:
            access_token = token_service.get_valid_access_token(self.connector)
            url = f"{GRAPH_BASE_URL}/auditLogs/signIns"
            headers = {"Authorization": f"Bearer {access_token}"}
            with httpx.Client(timeout=10) as client:
                response = client.get(url, headers=headers, params={"$top": 1})
            latency_ms = (time.time() - start_time) * 1000

            if response.status_code in (200, 400):  # 400 peut être un filtre invalide mais l'API est joignable
                return {
                    "reachable": True,
                    "latency_ms": round(latency_ms, 2),
                    "message": "Connexion Microsoft Graph API réussie.",
                }
            return {
                "reachable": False,
                "latency_ms": round(latency_ms, 2),
                "message": f"HTTP {response.status_code} : {response.text[:200]}",
            }
        except Exception as exc:
            latency_ms = (time.time() - start_time) * 1000
            return {
                "reachable": False,
                "latency_ms": round(latency_ms, 2),
                "message": str(exc),
            }
