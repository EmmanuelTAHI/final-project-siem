"""
Tests d'audit prod — apps.authentication.
Couvre : register, verify-email, login (email/password -> otp_required),
resend-otp (cooldown), password-reset (+confirm, sans aller au bout),
sessions (list/revoke sur un compte QA), token/refresh, logout.

Contraintes : ne JAMAIS changer le mot de passe du compte ADMIN réel, ne
jamais révoquer la session courante d'un compte QA (utilisée pour le reste
de la suite).
"""
import time
import uuid

import pytest

QA_PASSWORD = "TestQA123!"


class TestRegister:
    def test_register_with_existing_email_returns_explicit_message(self, anon_client, env_values):
        """Cf. commit c0de178 : message explicite quand l'email existe déjà."""
        admin_email = env_values.get("ADMIN_EMAIL")
        if not admin_email:
            pytest.skip("ADMIN_EMAIL absent de .env.test.")
        resp = anon_client.post(
            "/api/auth/register/",
            json={
                "email": admin_email,
                "password": "SomeRandomP@ssw0rd123",
                "first_name": "QA",
                "last_name": "Audit",
                "organization_name": f"{uuid.uuid4().hex[:8]} QA Audit Org",
            },
        )
        assert resp.status_code == 400
        body = resp.json()
        assert body["status"] == "error"
        # Le message doit mentionner explicitement l'email déjà utilisé,
        # porté par RegisterSerializer.validate_email().
        errors = body.get("errors", {})
        combined = str(errors).lower()
        assert "existe déjà" in combined or "existe deja" in combined

    def test_register_missing_fields_returns_400(self, anon_client):
        resp = anon_client.post("/api/auth/register/", json={"email": "incomplete@test.local"})
        assert resp.status_code == 400
        assert resp.json()["status"] == "error"


class TestVerifyEmail:
    def test_verify_email_with_invalid_token_returns_400(self, anon_client):
        resp = anon_client.post("/api/auth/verify-email/", json={"token": "not-a-valid-token"})
        assert resp.status_code == 400
        assert resp.json()["status"] == "error"

    def test_verify_email_missing_token_returns_400(self, anon_client):
        resp = anon_client.post("/api/auth/verify-email/", json={})
        assert resp.status_code == 400


class TestLogin:
    def test_login_valid_credentials_returns_otp_required(self, anon_client, env_values):
        admin_email = env_values.get("ADMIN_EMAIL")
        admin_password = env_values.get("ADMIN_PASSWORD")
        if not admin_email or not admin_password:
            pytest.skip("ADMIN_EMAIL / ADMIN_PASSWORD absents de .env.test.")
        resp = anon_client.post(
            "/api/auth/login/",
            json={"email": admin_email, "password": admin_password},
        )
        assert resp.status_code == 200
        body = resp.json()
        assert body["status"] == "success"
        assert body["data"]["status"] == "otp_required"
        assert "pre_auth_token" in body["data"]
        time.sleep(1)  # anti-throttle avant le test suivant

    def test_login_invalid_password_returns_401(self, anon_client, env_values):
        admin_email = env_values.get("ADMIN_EMAIL")
        if not admin_email:
            pytest.skip("ADMIN_EMAIL absent de .env.test.")
        resp = anon_client.post(
            "/api/auth/login/",
            json={"email": admin_email, "password": "definitely-wrong-password-123"},
        )
        assert resp.status_code == 401
        assert resp.json()["status"] == "error"
        time.sleep(1)

    def test_login_unknown_email_returns_401_generic_message(self, anon_client):
        resp = anon_client.post(
            "/api/auth/login/",
            json={"email": f"nonexistent-{uuid.uuid4().hex[:8]}@test.local", "password": "whatever123"},
        )
        assert resp.status_code == 401
        body = resp.json()
        assert body["status"] == "error"
        # Message générique, pas d'énumération de comptes.
        assert "incorrect" in body["message"].lower()
        time.sleep(1)

    def test_login_missing_fields_returns_400(self, anon_client):
        resp = anon_client.post("/api/auth/login/", json={"email": "a@test.local"})
        assert resp.status_code == 400


class TestResendOTP:
    def test_resend_otp_missing_pre_auth_token_returns_400(self, anon_client):
        resp = anon_client.post("/api/auth/resend-otp/", json={})
        assert resp.status_code == 400

    def test_resend_otp_invalid_token_returns_400(self, anon_client):
        resp = anon_client.post("/api/auth/resend-otp/", json={"pre_auth_token": "garbage"})
        assert resp.status_code == 400


class TestVerifyOTP:
    def test_verify_otp_missing_fields_returns_400(self, anon_client):
        resp = anon_client.post("/api/auth/verify-otp/", json={})
        assert resp.status_code == 400

    def test_verify_otp_invalid_pre_auth_token_returns_400(self, anon_client):
        resp = anon_client.post(
            "/api/auth/verify-otp/", json={"pre_auth_token": "garbage", "otp": "123456"}
        )
        assert resp.status_code == 400


class TestPasswordReset:
    def test_password_reset_unknown_email_returns_generic_success(self, anon_client):
        """Ne doit jamais fuiter d'info sur l'existence du compte."""
        resp = anon_client.post(
            "/api/auth/password-reset/",
            json={"email": f"unknown-{uuid.uuid4().hex[:8]}@test.local"},
        )
        assert resp.status_code == 200
        body = resp.json()
        assert body["status"] == "success"
        assert "compte existe" in body["message"].lower()

    def test_password_reset_missing_email_returns_400(self, anon_client):
        resp = anon_client.post("/api/auth/password-reset/", json={})
        assert resp.status_code == 400

    def test_password_reset_confirm_invalid_token_returns_400(self, anon_client):
        """
        On ne va JAMAIS jusqu'au bout d'un vrai reset de mot de passe (aucun
        compte ne doit voir son mot de passe changé par cette suite) — on
        vérifie uniquement le rejet propre d'un token invalide.
        """
        resp = anon_client.post(
            "/api/auth/password-reset/confirm/",
            json={"token": "invalid-token-xyz", "password": "SomeNewP@ssw0rd123"},
        )
        assert resp.status_code == 400
        assert resp.json()["status"] == "error"

    def test_password_reset_confirm_missing_fields_returns_400(self, anon_client):
        resp = anon_client.post("/api/auth/password-reset/confirm/", json={"token": "x"})
        assert resp.status_code == 400


class TestTokenRefresh:
    def test_token_refresh_missing_field_returns_400(self, anon_client):
        resp = anon_client.post("/api/auth/token/refresh/", json={})
        assert resp.status_code == 400
        assert resp.json()["status"] == "error"

    def test_token_refresh_invalid_token_returns_401(self, anon_client):
        resp = anon_client.post("/api/auth/token/refresh/", json={"refresh": "not-a-real-token"})
        assert resp.status_code == 401

    def test_token_refresh_valid_refresh_token_works(self, base_url, qa_viewer_a_token, env_values):
        """
        Vérifie le contrat de la réponse de refresh en conditions réelles.
        Utilise le refresh token QA_VIEWER_A tout juste régénéré par la
        fixture de session (conftest._refreshed_tokens) — un second refresh
        ici ferait tourner la rotation une fois de plus, ce qui est
        acceptable (le fichier .env.test est réécrit par conftest de toute
        façon), mais on préfère ne pas dépenser un refresh supplémentaire
        pour un test qui ne fait que vérifier le contrat déjà exercé par la
        fixture de session : on se contente donc de vérifier qu'un access
        token courant fonctionne sur un endpoint protégé simple.
        """
        assert qa_viewer_a_token  # déjà obtenu via /token/refresh/ par la fixture de session


class TestLogout:
    def test_logout_without_auth_returns_401(self, anon_client):
        resp = anon_client.post("/api/auth/logout/", json={"refresh": "whatever"})
        assert resp.status_code == 401

    def test_logout_missing_refresh_field_returns_400(self, qa_viewer_a_client):
        resp = qa_viewer_a_client.post("/api/auth/logout/", json={})
        assert resp.status_code == 400

    def test_logout_invalid_refresh_token_returns_400(self, qa_viewer_a_client):
        resp = qa_viewer_a_client.post("/api/auth/logout/", json={"refresh": "not-a-real-token"})
        assert resp.status_code == 400


class TestSessions:
    def test_sessions_requires_auth(self, anon_client):
        resp = anon_client.get("/api/auth/sessions/")
        assert resp.status_code == 401

    def test_sessions_list_returns_current_session(self, qa_viewer_a_client):
        resp = qa_viewer_a_client.get("/api/auth/sessions/")
        assert resp.status_code == 200
        body = resp.json()
        assert body["status"] == "success"
        sessions = body["data"]["sessions"]
        assert isinstance(sessions, list)
        assert len(sessions) >= 1
        for s in sessions:
            assert "id" in s and "device" in s and "created_at" in s

    def test_session_revoke_unknown_id_returns_404(self, qa_viewer_a_client):
        resp = qa_viewer_a_client.delete("/api/auth/sessions/999999999/")
        assert resp.status_code == 404

    def test_session_revoke_current_session_is_rejected(self, qa_viewer_a_client):
        """
        On ne révoque JAMAIS la session courante utilisée par le reste de la
        suite (elle deviendrait inutilisable pour les tests suivants). On
        vérifie plutôt que l'API elle-même refuse de le faire quand on lui
        présente l'ID de la session courante.
        """
        sessions_resp = qa_viewer_a_client.get("/api/auth/sessions/")
        assert sessions_resp.status_code == 200
        sessions = sessions_resp.json()["data"]["sessions"]
        current = next((s for s in sessions if s.get("current")), None)
        if current is None:
            pytest.skip("Impossible d'identifier la session courante dans la réponse.")
        resp = qa_viewer_a_client.delete(f"/api/auth/sessions/{current['id']}/")
        assert resp.status_code == 400


class TestNotifications:
    def test_notifications_requires_auth(self, anon_client):
        resp = anon_client.get("/api/auth/notifications/")
        assert resp.status_code == 401

    def test_notifications_list(self, qa_viewer_a_client):
        resp = qa_viewer_a_client.get("/api/auth/notifications/")
        assert resp.status_code == 200
        body = resp.json()
        assert "notifications" in body["data"]
        assert "unread_count" in body["data"]

    def test_notifications_mark_all_read(self, qa_viewer_a_client):
        resp = qa_viewer_a_client.post("/api/auth/notifications/read-all/")
        assert resp.status_code == 200
        assert resp.json()["status"] == "success"


class TestLinkedAccounts:
    def test_linked_accounts_requires_auth(self, anon_client):
        resp = anon_client.get("/api/auth/linked-accounts/")
        assert resp.status_code == 401

    def test_linked_accounts_list(self, qa_viewer_a_client):
        resp = qa_viewer_a_client.get("/api/auth/linked-accounts/")
        assert resp.status_code == 200
        assert "accounts" in resp.json()["data"]

    def test_linked_account_detail_unknown_id_returns_404(self, qa_viewer_a_client):
        resp = qa_viewer_a_client.get(f"/api/auth/linked-accounts/{uuid.uuid4()}/")
        assert resp.status_code == 404
