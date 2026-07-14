"""
Tests pour les alertes SOC.
"""
import pytest
from django.utils import timezone
from rest_framework import status
from rest_framework.test import APIClient

from apps.alerts.models import Alert, AlertComment
from apps.organizations.models import Organization
from apps.users.models import User


@pytest.fixture
def api_client():
    return APIClient()


@pytest.fixture
def org(db):
    return Organization.objects.create(name="Test Org", slug="test-org")


@pytest.fixture
def analyst_user(db, org):
    return User.objects.create_user(
        email="analyst@logplus.ci",
        password="Analyst@2025!",
        first_name="Analyst",
        last_name="SOC",
        role="analyst",
        organization=org,
    )


@pytest.fixture
def authenticated_analyst(api_client, analyst_user):
    api_client.force_authenticate(user=analyst_user)
    return api_client


@pytest.fixture
def sample_alert(db, org):
    return Alert.objects.create(
        organization=org,
        title="Test Brute Force Alert",
        description="5 login failures detected for user@test.ci",
        severity="high",
        status="open",
    )


class TestAlertModel:
    """Tests du modèle Alert."""

    def test_alert_creation(self, db, org):
        alert = Alert.objects.create(
            organization=org,
            title="Test Alert",
            description="Description de test",
            severity="high",
            status="open",
        )
        assert alert.id is not None
        assert alert.status == "open"
        assert alert.resolved_at is None

    def test_alert_resolve(self, db, org, analyst_user):
        alert = Alert.objects.create(
            organization=org,
            title="Resolvable Alert",
            description="Test",
            severity="medium",
            status="open",
        )
        alert.resolve(user=analyst_user, note="Faux positif confirmé.")
        assert alert.status == "resolved"
        assert alert.resolved_at is not None
        assert alert.resolution_note == "Faux positif confirmé."

    def test_time_to_resolve_calculated(self, db, org, analyst_user):
        alert = Alert.objects.create(
            organization=org,
            title="Timed Alert",
            description="Test timing",
            severity="low",
            status="open",
        )
        from datetime import timedelta
        alert.resolved_at = timezone.now() + timedelta(hours=2)
        alert.save()
        assert alert.time_to_resolve_hours is not None
        assert alert.time_to_resolve_hours > 0

    def test_alert_str(self, db, sample_alert):
        assert "HIGH" in str(sample_alert)
        assert "Test Brute Force Alert" in str(sample_alert)


class TestAlertAPI:
    """Tests des endpoints API d'alertes."""

    def test_list_alerts(self, authenticated_analyst, sample_alert):
        response = authenticated_analyst.get("/api/alerts/")
        assert response.status_code == status.HTTP_200_OK
        assert response.data["status"] == "success"

    def test_retrieve_alert(self, authenticated_analyst, sample_alert):
        response = authenticated_analyst.get(f"/api/alerts/{sample_alert.id}/")
        assert response.status_code == status.HTTP_200_OK
        assert response.data["data"]["id"] == str(sample_alert.id)

    def test_update_alert_status(self, authenticated_analyst, sample_alert):
        response = authenticated_analyst.patch(
            f"/api/alerts/{sample_alert.id}/",
            {"status": "in_progress"},
            format="json",
        )
        assert response.status_code == status.HTTP_200_OK
        assert response.data["data"]["status"] == "in_progress"

    def test_add_comment(self, authenticated_analyst, sample_alert):
        response = authenticated_analyst.post(
            f"/api/alerts/{sample_alert.id}/comments/",
            {"content": "Investigating the alert."},
            format="json",
        )
        assert response.status_code == status.HTTP_201_CREATED
        assert response.data["data"]["content"] == "Investigating the alert."

    def test_list_comments(self, authenticated_analyst, sample_alert, analyst_user):
        AlertComment.objects.create(
            alert=sample_alert,
            author=analyst_user,
            content="Premier commentaire.",
        )
        response = authenticated_analyst.get(f"/api/alerts/{sample_alert.id}/comments/")
        assert response.status_code == status.HTTP_200_OK

    def test_stats_endpoint(self, authenticated_analyst, sample_alert):
        response = authenticated_analyst.get("/api/alerts/stats/")
        assert response.status_code == status.HTTP_200_OK
        data = response.data["data"]
        assert "by_severity" in data
        assert "by_status" in data
        assert "mttr_hours" in data
        assert "false_positive_rate_percent" in data
