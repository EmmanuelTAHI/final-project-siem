"""
Tests d'audit prod — apps.soar.
CRUD playbooks (create QA_AUDIT_* -> delete), executions (lecture seule),
permission IsAdminOrReadOnly (analyst -> 403 sur create), stats.
Note : PlaybookViewSet renvoie du `Response(...)` DRF brut sur toggle/execute
(pas le format standardisé), mais create/list passent par le ModelViewSet
générique DRF standard (pagination par défaut, pas de wrapper success_response
custom ici non plus — PlaybookSerializer direct).
"""
import uuid

import pytest

from conftest import QA_PREFIX


def _playbook_payload(name):
    return {
        "name": name,
        "description": "Playbook QA d'audit — supprimé automatiquement en fin de test.",
        "trigger_type": "manual",
        "trigger_conditions": {},
        "actions": [],
        "is_active": False,
    }


@pytest.fixture
def qa_playbook(qa_admin_a_client):
    name = f"{QA_PREFIX}playbook_{uuid.uuid4().hex[:8]}"
    resp = qa_admin_a_client.post("/api/soar/playbooks/", json=_playbook_payload(name))
    assert resp.status_code == 201, resp.text
    playbook = resp.json() if isinstance(resp.json(), dict) and "id" in resp.json() else resp.json().get("data", resp.json())
    try:
        yield playbook
    finally:
        qa_admin_a_client.delete(f"/api/soar/playbooks/{playbook['id']}/")


class TestPlaybooksCRUD:
    def test_list_requires_auth(self, anon_client):
        resp = anon_client.get("/api/soar/playbooks/")
        assert resp.status_code == 401

    def test_list_as_viewer_allowed(self, qa_viewer_a_client):
        """IsAdminOrReadOnly -> lecture ouverte à tout utilisateur authentifié."""
        resp = qa_viewer_a_client.get("/api/soar/playbooks/")
        assert resp.status_code == 200

    def test_create_get_update_delete_cycle(self, qa_admin_a_client):
        name = f"{QA_PREFIX}playbook_{uuid.uuid4().hex[:8]}"
        created_id = None
        try:
            create_resp = qa_admin_a_client.post("/api/soar/playbooks/", json=_playbook_payload(name))
            assert create_resp.status_code == 201, create_resp.text
            created = create_resp.json()
            created_id = created["id"]
            assert created["name"] == name

            get_resp = qa_admin_a_client.get(f"/api/soar/playbooks/{created_id}/")
            assert get_resp.status_code == 200

            update_resp = qa_admin_a_client.put(
                f"/api/soar/playbooks/{created_id}/",
                json=_playbook_payload(name + "_updated"),
            )
            assert update_resp.status_code == 200
            assert update_resp.json()["name"] == name + "_updated"
        finally:
            if created_id:
                del_resp = qa_admin_a_client.delete(f"/api/soar/playbooks/{created_id}/")
                assert del_resp.status_code == 204
                created_id = None

    def test_create_as_analyst_forbidden(self, qa_analyst_a_client):
        """IsAdminOrReadOnly : écriture réservée aux admins."""
        resp = qa_analyst_a_client.post(
            "/api/soar/playbooks/", json=_playbook_payload(f"{QA_PREFIX}should_fail")
        )
        assert resp.status_code == 403

    def test_create_as_viewer_forbidden(self, qa_viewer_a_client):
        resp = qa_viewer_a_client.post(
            "/api/soar/playbooks/", json=_playbook_payload(f"{QA_PREFIX}should_fail")
        )
        assert resp.status_code == 403

    def test_delete_as_analyst_forbidden(self, qa_playbook, qa_analyst_a_client):
        resp = qa_analyst_a_client.delete(f"/api/soar/playbooks/{qa_playbook['id']}/")
        assert resp.status_code == 403


class TestPlaybookActions:
    def test_toggle_flips_is_active(self, qa_playbook, qa_admin_a_client):
        original_state = qa_playbook["is_active"]
        resp = qa_admin_a_client.post(f"/api/soar/playbooks/{qa_playbook['id']}/toggle/")
        assert resp.status_code == 200
        assert resp.json()["is_active"] == (not original_state)

    def test_toggle_as_analyst_forbidden(self, qa_playbook, qa_analyst_a_client):
        resp = qa_analyst_a_client.post(f"/api/soar/playbooks/{qa_playbook['id']}/toggle/")
        assert resp.status_code == 403

    def test_execute_missing_alert_id_returns_400(self, qa_playbook, qa_admin_a_client):
        resp = qa_admin_a_client.post(f"/api/soar/playbooks/{qa_playbook['id']}/execute/", json={})
        assert resp.status_code == 400

    def test_execute_as_analyst_forbidden(self, qa_playbook, qa_analyst_a_client):
        """IsAdminOrReadOnly : execute() est un POST -> réservé admin."""
        resp = qa_analyst_a_client.post(
            f"/api/soar/playbooks/{qa_playbook['id']}/execute/", json={"alert_id": str(uuid.uuid4())}
        )
        assert resp.status_code == 403


class TestPlaybookExecutions:
    def test_list_requires_auth(self, anon_client):
        resp = anon_client.get("/api/soar/executions/")
        assert resp.status_code == 401

    def test_list_as_analyst_allowed(self, qa_analyst_a_client):
        resp = qa_analyst_a_client.get("/api/soar/executions/")
        assert resp.status_code == 200

    def test_list_as_viewer_forbidden(self, qa_viewer_a_client):
        """PlaybookExecutionViewSet.permission_classes = [IsAnalyst]."""
        resp = qa_viewer_a_client.get("/api/soar/executions/")
        assert resp.status_code == 403


class TestSOARStats:
    def test_requires_auth(self, anon_client):
        resp = anon_client.get("/api/soar/stats/")
        assert resp.status_code == 401

    def test_as_analyst_allowed(self, qa_analyst_a_client):
        resp = qa_analyst_a_client.get("/api/soar/stats/")
        assert resp.status_code == 200
        body = resp.json()
        for key in ("total_playbooks", "active_playbooks", "executions_24h", "success_rate"):
            assert key in body

    def test_as_viewer_forbidden(self, qa_viewer_a_client):
        resp = qa_viewer_a_client.get("/api/soar/stats/")
        assert resp.status_code == 403
