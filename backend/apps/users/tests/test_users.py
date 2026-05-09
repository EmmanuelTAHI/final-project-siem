"""
Tests unitaires pour l'application users.
"""
import pytest
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APIClient

from apps.users.models import AuditTrail, User


@pytest.fixture
def api_client():
    return APIClient()


@pytest.fixture
def admin_user(db):
    return User.objects.create_user(
        email="admin@logplus.ci",
        password="Admin@2025!",
        first_name="Admin",
        last_name="Log+",
        role="admin",
    )


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
def viewer_user(db):
    return User.objects.create_user(
        email="viewer@logplus.ci",
        password="Viewer@2025!",
        first_name="Viewer",
        last_name="Guest",
        role="viewer",
    )


@pytest.fixture
def authenticated_admin(api_client, admin_user):
    api_client.force_authenticate(user=admin_user)
    return api_client


@pytest.fixture
def authenticated_analyst(api_client, analyst_user):
    api_client.force_authenticate(user=analyst_user)
    return api_client


class TestUserCreation:
    """Tests de création d'utilisateurs."""

    def test_create_user_with_valid_data(self, db):
        user = User.objects.create_user(
            email="test@example.com",
            password="SecureP@ss123",
            first_name="Test",
            last_name="User",
        )
        assert user.email == "test@example.com"
        assert user.role == "viewer"
        assert user.is_active is True
        assert user.check_password("SecureP@ss123")

    def test_create_superuser(self, db):
        user = User.objects.create_superuser(
            email="super@example.com",
            password="SuperP@ss123",
            first_name="Super",
            last_name="Admin",
        )
        assert user.role == "admin"
        assert user.is_staff is True
        assert user.is_superuser is True

    def test_user_email_is_unique(self, db, admin_user):
        with pytest.raises(Exception):
            User.objects.create_user(
                email="admin@logplus.ci",
                password="Another@Pass123",
                first_name="Duplicate",
                last_name="User",
            )

    def test_user_str_representation(self, db, admin_user):
        assert "admin@logplus.ci" in str(admin_user)
        assert "admin" in str(admin_user)


class TestUserAPI:
    """Tests des endpoints API utilisateurs."""

    def test_list_users_as_admin(self, authenticated_admin, admin_user, analyst_user):
        response = authenticated_admin.get("/api/users/")
        assert response.status_code == status.HTTP_200_OK
        assert response.data["status"] == "success"

    def test_list_users_forbidden_for_analyst(self, authenticated_analyst):
        response = authenticated_analyst.get("/api/users/")
        assert response.status_code == status.HTTP_403_FORBIDDEN

    def test_get_me_returns_current_user(self, authenticated_analyst, analyst_user):
        response = authenticated_analyst.get("/api/users/me/")
        assert response.status_code == status.HTTP_200_OK
        assert response.data["data"]["email"] == analyst_user.email

    def test_create_user_as_admin(self, authenticated_admin):
        payload = {
            "email": "newuser@logplus.ci",
            "first_name": "New",
            "last_name": "User",
            "role": "analyst",
            "password": "NewUser@2025!",
            "password_confirm": "NewUser@2025!",
        }
        response = authenticated_admin.post("/api/users/", data=payload, format="json")
        assert response.status_code == status.HTTP_201_CREATED
        assert response.data["data"]["email"] == "newuser@logplus.ci"

    def test_create_user_password_mismatch(self, authenticated_admin):
        payload = {
            "email": "mismatch@logplus.ci",
            "first_name": "Mis",
            "last_name": "Match",
            "role": "viewer",
            "password": "Pass@2025!",
            "password_confirm": "Different@2025!",
        }
        response = authenticated_admin.post("/api/users/", data=payload, format="json")
        assert response.status_code == status.HTTP_400_BAD_REQUEST


class TestAuditTrail:
    """Tests du journal d'audit."""

    def test_audit_trail_log_creates_entry(self, db, admin_user):
        entry = AuditTrail.log(
            action="test_action",
            user=admin_user,
            target_model="User",
            target_id=admin_user.id,
            ip_address="127.0.0.1",
        )
        assert entry.pk is not None
        assert entry.action == "test_action"
        assert entry.user == admin_user
        assert entry.ip_address == "127.0.0.1"

    def test_audit_trail_str(self, db, admin_user):
        entry = AuditTrail.log(action="login", user=admin_user)
        assert "login" in str(entry)
        assert "admin@logplus.ci" in str(entry)

    def test_audit_trail_viewset_requires_admin(self, authenticated_analyst):
        response = authenticated_analyst.get("/api/users/audit-trail/")
        assert response.status_code == status.HTTP_403_FORBIDDEN
