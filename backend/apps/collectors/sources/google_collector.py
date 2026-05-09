"""
Collecteur Google Workspace via Google Admin Reports API.
Endpoint : GET https://admin.googleapis.com/admin/reports/v1/activity/users/all/applications/login
"""
import logging
import time
from typing import Generator

import httpx
import django.utils.timezone as timezone

from apps.authentication.services.token_service import token_service

from .base_collector import BaseCollector

logger = logging.getLogger(__name__)

ADMIN_REPORTS_BASE_URL = "https://admin.googleapis.com/admin/reports/v1"


class GoogleCollector(BaseCollector):
    """
    Collecteur des logs d'activité Google Workspace.
    Utilise Google Admin Reports API avec pagination nextPageToken.
    """

    def fetch_logs(self) -> Generator[dict, None, None]:
        """
        Récupère les logs de connexion Google Workspace.
        Gère automatiquement la pagination via nextPageToken.
        """
        access_token = token_service.get_valid_access_token(self.connector)

        last_collected = self.connector.last_collected_at
        if last_collected:
            start_time = last_collected.strftime("%Y-%m-%dT%H:%M:%S.000Z")
        else:
            from datetime import timedelta
            start = timezone.now() - timedelta(hours=24)
            start_time = start.strftime("%Y-%m-%dT%H:%M:%S.000Z")

        end_time = timezone.now().strftime("%Y-%m-%dT%H:%M:%S.000Z")
        url = f"{ADMIN_REPORTS_BASE_URL}/activity/users/all/applications/login"

        headers = {
            "Authorization": f"Bearer {access_token}",
            "Accept": "application/json",
        }
        params = {
            "startTime": start_time,
            "endTime": end_time,
            "maxResults": 1000,
        }

        page_count = 0
        with httpx.Client(timeout=60, follow_redirects=True) as client:
            while True:
                response = client.get(url, headers=headers, params=params)

                if response.status_code == 401:
                    logger.warning("Token Google expiré, tentative de refresh...")
                    token_service.refresh_token(self.connector)
                    access_token = token_service.get_valid_access_token(self.connector)
                    headers["Authorization"] = f"Bearer {access_token}"
                    response = client.get(url, headers=headers, params=params)

                if response.status_code == 429:
                    retry_after = int(response.headers.get("Retry-After", 60))
                    logger.warning("Rate limit Google Admin API. Attente %ds...", retry_after)
                    time.sleep(retry_after)
                    continue

                response.raise_for_status()
                data = response.json()

                for item in data.get("items", []):
                    yield self._enrich_log(item)

                next_page_token = data.get("nextPageToken")
                if not next_page_token:
                    break

                params["pageToken"] = next_page_token
                # Supprimer startTime et endTime pour les pages suivantes (non nécessaires)
                params.pop("startTime", None)
                params.pop("endTime", None)
                page_count += 1
                logger.debug("Google Workspace page %d collectée (%d logs)", page_count, len(data.get("items", [])))

    def _enrich_log(self, log_entry: dict) -> dict:
        """Ajoute des métadonnées internes au log brut."""
        log_entry["_source"] = "google_workspace"
        return log_entry

    def test_connection(self) -> dict:
        """Teste la connexion à Google Admin Reports API."""
        start_time = time.time()
        try:
            access_token = token_service.get_valid_access_token(self.connector)
            url = f"{ADMIN_REPORTS_BASE_URL}/activity/users/all/applications/login"
            headers = {"Authorization": f"Bearer {access_token}"}
            params = {"maxResults": 1}
            with httpx.Client(timeout=10) as client:
                response = client.get(url, headers=headers, params=params)
            latency_ms = (time.time() - start_time) * 1000

            if response.status_code == 200:
                return {
                    "reachable": True,
                    "latency_ms": round(latency_ms, 2),
                    "message": "Connexion Google Admin Reports API réussie.",
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
