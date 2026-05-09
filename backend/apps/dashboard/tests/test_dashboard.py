"""
Tests des vues du tableau de bord SOC.
"""
import pytest
from rest_framework import status
from rest_framework.test import APIClient

from apps.users.models import User


@pytest.fixture
def api_client():
    return APIClient()


@pytest.fixture
def analyst_user(db):
    return User.objects.create_user(
        email="analyst@logplus.ci",
        password="Analyst@2025!",
        first_name="Analyst",
        last_name="SOC",
        role="analyst",
    )


@pytest.fixture
def authenticated_client(api_client, analyst_user):
    api_client.force_authenticate(user=analyst_user)
    return api_client


class TestDashboardSummary:
    """Tests du endpoint /api/dashboard/summary/"""

    def test_summary_returns_200(self, authenticated_client, db):
        response = authenticated_client.get("/api/dashboard/summary/")
        assert response.status_code == status.HTTP_200_OK
        assert response.data["status"] == "success"

    def test_summary_has_required_keys(self, authenticated_client, db):
        response = authenticated_client.get("/api/dashboard/summary/")
        data = response.data["data"]
        assert "alerts" in data
        assert "logs" in data
        assert "connectors" in data
        assert "ml" in data
        assert "generated_at" in data

    def test_summary_alerts_structure(self, authenticated_client, db):
        response = authenticated_client.get("/api/dashboard/summary/")
        alerts = response.data["data"]["alerts"]
        assert "total_open" in alerts
        assert "open_by_severity" in alerts
        assert "false_positive_rate_percent" in alerts

    def test_summary_requires_authentication(self, api_client):
        response = api_client.get("/api/dashboard/summary/")
        assert response.status_code == status.HTTP_401_UNAUTHORIZED


class TestDashboardTimeline:
    """Tests du endpoint /api/dashboard/timeline/"""

    def test_timeline_24h(self, authenticated_client, db):
        response = authenticated_client.get("/api/dashboard/timeline/?period=24h")
        assert response.status_code == status.HTTP_200_OK
        data = response.data["data"]
        assert data["period"] == "24h"
        assert "logs" in data
        assert "alerts" in data

    def test_timeline_7d(self, authenticated_client, db):
        response = authenticated_client.get("/api/dashboard/timeline/?period=7d")
        assert response.status_code == status.HTTP_200_OK
        assert response.data["data"]["period"] == "7d"

    def test_timeline_30d(self, authenticated_client, db):
        response = authenticated_client.get("/api/dashboard/timeline/?period=30d")
        assert response.status_code == status.HTTP_200_OK
        assert response.data["data"]["period"] == "30d"

    def test_timeline_invalid_period_defaults_24h(self, authenticated_client, db):
        response = authenticated_client.get("/api/dashboard/timeline/?period=invalid")
        assert response.status_code == status.HTTP_200_OK
        assert response.data["data"]["period"] == "24h"


class TestDashboardGeoMap:
    """Tests du endpoint /api/dashboard/geo-map/"""

    def test_geo_map_returns_200(self, authenticated_client, db):
        response = authenticated_client.get("/api/dashboard/geo-map/")
        assert response.status_code == status.HTTP_200_OK

    def test_geo_map_structure(self, authenticated_client, db):
        response = authenticated_client.get("/api/dashboard/geo-map/")
        data = response.data["data"]
        assert "period" in data
        assert "countries" in data
        assert isinstance(data["countries"], list)
