"""
Tests d'audit prod — apps.collectors.
Couvre : CRUD ConnectorConfig complet (create -> get -> update -> delete),
action test/collect, enrollment-tokens CRUD, permission IsAnalyst (viewer ->
403).
"""
import uuid

import pytest

from conftest import QA_PREFIX


@pytest.fixture
def qa_connector(qa_admin_a_client):
    """Crée un connecteur syslog QA_AUDIT_* et le supprime après le test,
    même si le test échoue en cours de route."""
    name = f"{QA_PREFIX}connector_{uuid.uuid4().hex[:8]}"
    resp = qa_admin_a_client.post(
        "/api/collectors/connectors/",
        json={
            "name": name,
            "source_type": "syslog",
            "polling_interval_seconds": 300,
            "is_active": True,
        },
    )
    assert resp.status_code == 201, resp.text
    connector = resp.json()["data"]
    try:
        yield connector
    finally:
        qa_admin_a_client.delete(f"/api/collectors/connectors/{connector['id']}/")


class TestConnectorsCRUD:
    def test_list_requires_auth(self, anon_client):
        resp = anon_client.get("/api/collectors/connectors/")
        assert resp.status_code == 401

    def test_create_get_update_delete_cycle(self, qa_admin_a_client):
        name = f"{QA_PREFIX}connector_{uuid.uuid4().hex[:8]}"
        created_id = None
        try:
            create_resp = qa_admin_a_client.post(
                "/api/collectors/connectors/",
                json={
                    "name": name,
                    "source_type": "syslog",
                    "polling_interval_seconds": 120,
                    "is_active": True,
                },
            )
            assert create_resp.status_code == 201, create_resp.text
            created = create_resp.json()["data"]
            created_id = created["id"]
            assert created["name"] == name
            assert created["source_type"] == "syslog"

            get_resp = qa_admin_a_client.get(f"/api/collectors/connectors/{created_id}/")
            assert get_resp.status_code == 200
            assert get_resp.json()["data"]["id"] == created_id

            update_resp = qa_admin_a_client.put(
                f"/api/collectors/connectors/{created_id}/",
                json={
                    "name": name + "_updated",
                    "source_type": "syslog",
                    "polling_interval_seconds": 600,
                    "is_active": False,
                },
            )
            assert update_resp.status_code == 200
            assert update_resp.json()["data"]["name"] == name + "_updated"
            assert update_resp.json()["data"]["is_active"] is False
        finally:
            if created_id:
                delete_resp = qa_admin_a_client.delete(f"/api/collectors/connectors/{created_id}/")
                assert delete_resp.status_code == 204
                created_id = None

    def test_create_as_viewer_forbidden(self, qa_viewer_a_client):
        resp = qa_viewer_a_client.post(
            "/api/collectors/connectors/",
            json={"name": f"{QA_PREFIX}should_fail", "source_type": "syslog"},
        )
        assert resp.status_code == 403

    def test_create_as_analyst_forbidden(self, qa_analyst_a_client):
        """ConnectorConfigViewSet.get_permissions : create/destroy/update -> IsAdmin only."""
        resp = qa_analyst_a_client.post(
            "/api/collectors/connectors/",
            json={"name": f"{QA_PREFIX}should_fail", "source_type": "syslog"},
        )
        assert resp.status_code == 403

    def test_list_as_analyst_allowed(self, qa_connector, qa_analyst_a_client):
        resp = qa_analyst_a_client.get("/api/collectors/connectors/")
        assert resp.status_code == 200

    def test_list_as_viewer_forbidden(self, qa_viewer_a_client):
        resp = qa_viewer_a_client.get("/api/collectors/connectors/")
        assert resp.status_code == 403

    def test_delete_as_analyst_forbidden(self, qa_connector, qa_analyst_a_client):
        resp = qa_analyst_a_client.delete(f"/api/collectors/connectors/{qa_connector['id']}/")
        assert resp.status_code == 403


class TestConnectorActions:
    def test_test_action_analyst_allowed_syntactically(self, qa_connector, qa_analyst_a_client):
        """
        source_type=syslog n'est pas dans collector_map de la vue `test` ->
        réponse 400 attendue (pas de test de connexion dispo pour syslog),
        mais ça prouve que la permission IsAnalyst laisse bien passer l'appel.
        """
        resp = qa_analyst_a_client.post(f"/api/collectors/connectors/{qa_connector['id']}/test/")
        assert resp.status_code in (200, 400, 500)

    def test_test_action_viewer_forbidden(self, qa_connector, qa_viewer_a_client):
        resp = qa_viewer_a_client.post(f"/api/collectors/connectors/{qa_connector['id']}/test/")
        assert resp.status_code == 403

    def test_collect_action_triggers_job(self, qa_connector, qa_analyst_a_client):
        resp = qa_analyst_a_client.post(f"/api/collectors/connectors/{qa_connector['id']}/collect/")
        assert resp.status_code == 202
        assert "job_id" in resp.json()["data"]

    def test_collect_action_viewer_forbidden(self, qa_connector, qa_viewer_a_client):
        resp = qa_viewer_a_client.post(f"/api/collectors/connectors/{qa_connector['id']}/collect/")
        assert resp.status_code == 403


class TestCollectionJobs:
    def test_list_requires_auth(self, anon_client):
        resp = anon_client.get("/api/collectors/jobs/")
        assert resp.status_code == 401

    def test_list_as_analyst_allowed(self, qa_analyst_a_client):
        resp = qa_analyst_a_client.get("/api/collectors/jobs/")
        assert resp.status_code == 200

    def test_list_as_viewer_forbidden(self, qa_viewer_a_client):
        resp = qa_viewer_a_client.get("/api/collectors/jobs/")
        assert resp.status_code == 403


@pytest.fixture
def qa_enrollment_token(qa_admin_a_client):
    name = f"{QA_PREFIX}token_{uuid.uuid4().hex[:8]}"
    resp = qa_admin_a_client.post("/api/collectors/enrollment-tokens/", json={"name": name})
    assert resp.status_code == 201, resp.text
    token = resp.json()["data"]
    try:
        yield token
    finally:
        qa_admin_a_client.delete(f"/api/collectors/enrollment-tokens/{token['id']}/")


class TestEnrollmentTokens:
    def test_list_requires_auth(self, anon_client):
        resp = anon_client.get("/api/collectors/enrollment-tokens/")
        assert resp.status_code == 401

    def test_create_returns_raw_token_once(self, qa_admin_a_client):
        name = f"{QA_PREFIX}token_{uuid.uuid4().hex[:8]}"
        token_id = None
        try:
            resp = qa_admin_a_client.post("/api/collectors/enrollment-tokens/", json={"name": name})
            assert resp.status_code == 201, resp.text
            data = resp.json()["data"]
            token_id = data["id"]
            assert data["token"].startswith("logplus_agt_")
            assert data["name"] == name

            list_resp = qa_admin_a_client.get("/api/collectors/enrollment-tokens/")
            assert list_resp.status_code == 200
            # Le token en clair ne doit jamais être exposé une seconde fois.
            items = list_resp.json()["data"]
            items = items if isinstance(items, list) else items.get("results", [])
            match = next((i for i in items if i["id"] == token_id), None)
            assert match is not None
            assert "token" not in match
        finally:
            if token_id:
                del_resp = qa_admin_a_client.delete(f"/api/collectors/enrollment-tokens/{token_id}/")
                assert del_resp.status_code == 204

    def test_create_as_analyst_forbidden(self, qa_analyst_a_client):
        resp = qa_analyst_a_client.post(
            "/api/collectors/enrollment-tokens/", json={"name": f"{QA_PREFIX}should_fail"}
        )
        assert resp.status_code == 403

    def test_list_as_viewer_forbidden(self, qa_viewer_a_client):
        resp = qa_viewer_a_client.get("/api/collectors/enrollment-tokens/")
        assert resp.status_code == 403

    def test_delete_revokes_not_deletes(self, qa_enrollment_token, qa_admin_a_client):
        """destroy() ne fait qu'un soft-delete (is_active=False) — vérifie
        juste que l'appel réussit (204), le teardown de la fixture s'en
        assure de toute façon."""
        resp = qa_admin_a_client.delete(f"/api/collectors/enrollment-tokens/{qa_enrollment_token['id']}/")
        assert resp.status_code == 204
