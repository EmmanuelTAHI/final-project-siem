"""
Tests des vues d'authentification JWT.
"""
import pytest
from rest_framework import status
from rest_framework.test import APIClient

from apps.users.models import User


@pytest.fixture
def api_client():
    return APIClient()


@pytest.fixture
def active_user(db):
    return User.objects.create_user(
        email="testuser@logplus.ci",
        password="TestUser@2025!",
        first_name="Test",
        last_name="User",
        role="analyst",
    )


@pytest.fixture
def inactive_user(db):
    return User.objects.create_user(
        email="inactive@logplus.ci",
        password="Inactive@2025!",
        first_name="Inactive",
        last_name="User",
        role="viewer",
        is_active=False,
    )


class TestLoginView:
    """Tests de l'endpoint POST /api/auth/login/"""

    def test_login_with_valid_credentials(self, api_client, active_user):
        response = api_client.post(
            "/api/auth/login/",
            {"email": "testuser@logplus.ci", "password": "TestUser@2025!"},
            format="json",
        )
        assert response.status_code == status.HTTP_200_OK
        assert response.data["status"] == "success"
        assert "access_token" in response.data["data"]
        assert "refresh_token" in response.data["data"]
        assert response.data["data"]["user"]["email"] == "testuser@logplus.ci"

    def test_login_with_wrong_password(self, api_client, active_user):
        response = api_client.post(
            "/api/auth/login/",
            {"email": "testuser@logplus.ci", "password": "WrongPassword!"},
            format="json",
        )
        assert response.status_code == status.HTTP_401_UNAUTHORIZED
        assert response.data["status"] == "error"

    def test_login_with_nonexistent_email(self, api_client, db):
        response = api_client.post(
            "/api/auth/login/",
            {"email": "notfound@logplus.ci", "password": "SomePassword!"},
            format="json",
        )
        assert response.status_code == status.HTTP_401_UNAUTHORIZED

    def test_login_inactive_user(self, api_client, inactive_user):
        response = api_client.post(
            "/api/auth/login/",
            {"email": "inactive@logplus.ci", "password": "Inactive@2025!"},
            format="json",
        )
        assert response.status_code == status.HTTP_403_FORBIDDEN

    def test_login_missing_fields(self, api_client, db):
        response = api_client.post("/api/auth/login/", {}, format="json")
        assert response.status_code == status.HTTP_400_BAD_REQUEST


class TestTokenRefreshView:
    """Tests du renouvellement de token."""

    def test_refresh_with_valid_token(self, api_client, active_user):
        login_response = api_client.post(
            "/api/auth/login/",
            {"email": "testuser@logplus.ci", "password": "TestUser@2025!"},
            format="json",
        )
        refresh_token = login_response.data["data"]["refresh_token"]
        response = api_client.post(
            "/api/auth/token/refresh/",
            {"refresh": refresh_token},
            format="json",
        )
        assert response.status_code == status.HTTP_200_OK
        assert "access_token" in response.data["data"]

    def test_refresh_with_invalid_token(self, api_client, db):
        response = api_client.post(
            "/api/auth/token/refresh/",
            {"refresh": "invalid.token.here"},
            format="json",
        )
        assert response.status_code == status.HTTP_401_UNAUTHORIZED


class TestLogoutView:
    """Tests de la déconnexion."""

    def test_logout_with_valid_refresh_token(self, api_client, active_user):
        login_response = api_client.post(
            "/api/auth/login/",
            {"email": "testuser@logplus.ci", "password": "TestUser@2025!"},
            format="json",
        )
        access_token = login_response.data["data"]["access_token"]
        refresh_token = login_response.data["data"]["refresh_token"]

        api_client.credentials(HTTP_AUTHORIZATION=f"Bearer {access_token}")
        response = api_client.post(
            "/api/auth/logout/",
            {"refresh": refresh_token},
            format="json",
        )
        assert response.status_code == status.HTTP_200_OK
        assert response.data["status"] == "success"

    def test_logout_requires_authentication(self, api_client, db):
        response = api_client.post(
            "/api/auth/logout/",
            {"refresh": "some.token.here"},
            format="json",
        )
        assert response.status_code == status.HTTP_401_UNAUTHORIZED
