"""
Tests d'audit prod — apps.users.
Couvre : me (GET/PATCH), liste users (permission par rôle), invite (POST,
permission admin), audit-trail (GET, permission admin).
"""
import uuid


class TestMe:
    def test_me_requires_auth(self, anon_client):
        resp = anon_client.get("/api/users/me/")
        assert resp.status_code == 401

    def test_me_get_returns_profile(self, qa_viewer_a_client):
        resp = qa_viewer_a_client.get("/api/users/me/")
        assert resp.status_code == 200
        body = resp.json()
        assert body["status"] == "success"
        assert "email" in body["data"]
        assert body["data"]["role"] == "viewer"

    def test_me_patch_updates_and_restores_first_name(self, qa_analyst_a_client):
        """
        Modifie un champ inoffensif (first_name) sur un compte QA puis remet
        la valeur d'origine — ne doit jamais laisser le compte altéré.
        """
        original = qa_analyst_a_client.get("/api/users/me/").json()["data"]["first_name"]
        marker = f"QAAudit-{uuid.uuid4().hex[:6]}"
        try:
            resp = qa_analyst_a_client.patch("/api/users/me/", json={"first_name": marker})
            assert resp.status_code == 200
            assert resp.json()["data"]["first_name"] == marker
        finally:
            restore = qa_analyst_a_client.patch("/api/users/me/", json={"first_name": original})
            assert restore.status_code == 200
            assert restore.json()["data"]["first_name"] == original

    def test_me_patch_cannot_self_promote_role(self, qa_viewer_a_client):
        """SelfProfileUpdateSerializer n'expose pas `role` — un viewer ne doit
        jamais pouvoir s'auto-promouvoir admin via /me/."""
        resp = qa_viewer_a_client.patch("/api/users/me/", json={"role": "admin"})
        assert resp.status_code == 200
        assert resp.json()["data"]["role"] == "viewer"


class TestUserList:
    def test_list_requires_auth(self, anon_client):
        resp = anon_client.get("/api/users/")
        assert resp.status_code == 401

    def test_list_as_admin_succeeds(self, qa_admin_a_client):
        resp = qa_admin_a_client.get("/api/users/")
        assert resp.status_code == 200

    def test_list_as_analyst_forbidden(self, qa_analyst_a_client):
        resp = qa_analyst_a_client.get("/api/users/")
        assert resp.status_code == 403

    def test_list_as_viewer_forbidden(self, qa_viewer_a_client):
        resp = qa_viewer_a_client.get("/api/users/")
        assert resp.status_code == 403

    def test_list_only_shows_same_organization(self, qa_admin_a_client, qa_admin_b_token):
        """Isolation multi-tenant basique : org A ne doit pas voir les
        emails des comptes QA de l'org B dans sa liste d'utilisateurs."""
        resp = qa_admin_a_client.get("/api/users/")
        assert resp.status_code == 200
        body = resp.json()
        items = body["data"] if isinstance(body["data"], list) else body["data"].get("results", [])
        emails = {u["email"] for u in items}
        assert not any("qa_admin_b" in e.lower() or "qa_analyst_b" in e.lower() for e in emails)


class TestInviteUser:
    def test_invite_requires_auth(self, anon_client):
        resp = anon_client.post("/api/users/invite/", json={})
        assert resp.status_code == 401

    def test_invite_as_analyst_forbidden(self, qa_analyst_a_client):
        resp = qa_analyst_a_client.post(
            "/api/users/invite/",
            json={
                "email": f"qa-audit-invite-{uuid.uuid4().hex[:8]}@test.local",
                "first_name": "QA",
                "last_name": "Invite",
                "role": "viewer",
            },
        )
        assert resp.status_code == 403

    def test_invite_as_viewer_forbidden(self, qa_viewer_a_client):
        resp = qa_viewer_a_client.post(
            "/api/users/invite/",
            json={
                "email": f"qa-audit-invite-{uuid.uuid4().hex[:8]}@test.local",
                "first_name": "QA",
                "last_name": "Invite",
                "role": "viewer",
            },
        )
        assert resp.status_code == 403

    def test_invite_existing_email_returns_400(self, qa_admin_a_client, env_values):
        admin_email = env_values.get("ADMIN_EMAIL")
        if not admin_email:
            import pytest
            pytest.skip("ADMIN_EMAIL absent de .env.test.")
        resp = qa_admin_a_client.post(
            "/api/users/invite/",
            json={
                "email": admin_email,
                "first_name": "QA",
                "last_name": "Invite",
                "role": "viewer",
            },
        )
        assert resp.status_code == 400


class TestAuditTrail:
    def test_audit_trail_requires_auth(self, anon_client):
        resp = anon_client.get("/api/users/audit-trail/")
        assert resp.status_code == 401

    def test_audit_trail_as_admin_succeeds(self, qa_admin_a_client):
        resp = qa_admin_a_client.get("/api/users/audit-trail/")
        assert resp.status_code == 200

    def test_audit_trail_as_analyst_forbidden(self, qa_analyst_a_client):
        resp = qa_analyst_a_client.get("/api/users/audit-trail/")
        assert resp.status_code == 403

    def test_audit_trail_as_viewer_forbidden(self, qa_viewer_a_client):
        resp = qa_viewer_a_client.get("/api/users/audit-trail/")
        assert resp.status_code == 403
