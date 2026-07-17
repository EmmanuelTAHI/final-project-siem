"""
Tests d'audit prod — apps.hunting.
CRUD queries (create QA_AUDIT_* -> delete), run (POST ad-hoc, sans
sauvegarde), execute (POST sur une query sauvegardée), results (GET).
HuntingQueryViewSet est un ModelViewSet standard DRF (pas de success_response
custom) : create/update/retrieve renvoient le serializer.data brut, list est
paginé par la pagination globale (StandardResultsPagination -> wrapper
{status,data,message,pagination}).
"""
import uuid

import pytest

from conftest import QA_PREFIX


def _query_payload(name):
    return {
        "name": name,
        "description": "Requête de chasse QA d'audit — supprimée en fin de test.",
        "query_params": {"severity": "low"},
        "mitre_tactic": "",
        "mitre_technique": "",
    }


@pytest.fixture
def qa_hunting_query(qa_analyst_a_client):
    name = f"{QA_PREFIX}hunt_{uuid.uuid4().hex[:8]}"
    resp = qa_analyst_a_client.post("/api/hunting/queries/", json=_query_payload(name))
    assert resp.status_code == 201, resp.text
    query = resp.json()
    try:
        yield query
    finally:
        qa_analyst_a_client.delete(f"/api/hunting/queries/{query['id']}/")


class TestHuntingQueriesCRUD:
    def test_list_requires_auth(self, anon_client):
        resp = anon_client.get("/api/hunting/queries/")
        assert resp.status_code == 401

    def test_list_as_viewer_forbidden(self, qa_viewer_a_client):
        resp = qa_viewer_a_client.get("/api/hunting/queries/")
        assert resp.status_code == 403

    def test_list_as_analyst_allowed(self, qa_analyst_a_client):
        resp = qa_analyst_a_client.get("/api/hunting/queries/")
        assert resp.status_code == 200

    def test_create_get_update_delete_cycle(self, qa_analyst_a_client):
        name = f"{QA_PREFIX}hunt_{uuid.uuid4().hex[:8]}"
        created_id = None
        try:
            create_resp = qa_analyst_a_client.post("/api/hunting/queries/", json=_query_payload(name))
            assert create_resp.status_code == 201, create_resp.text
            created = create_resp.json()
            created_id = created["id"]
            assert created["name"] == name

            get_resp = qa_analyst_a_client.get(f"/api/hunting/queries/{created_id}/")
            assert get_resp.status_code == 200

            update_resp = qa_analyst_a_client.put(
                f"/api/hunting/queries/{created_id}/", json=_query_payload(name + "_updated")
            )
            assert update_resp.status_code == 200
            assert update_resp.json()["name"] == name + "_updated"
        finally:
            if created_id:
                del_resp = qa_analyst_a_client.delete(f"/api/hunting/queries/{created_id}/")
                assert del_resp.status_code == 204
                created_id = None

    def test_create_as_viewer_forbidden(self, qa_viewer_a_client):
        resp = qa_viewer_a_client.post(
            "/api/hunting/queries/", json=_query_payload(f"{QA_PREFIX}should_fail")
        )
        assert resp.status_code == 403


class TestHuntingQueryActions:
    def test_execute_returns_results_shape(self, qa_hunting_query, qa_analyst_a_client):
        resp = qa_analyst_a_client.post(f"/api/hunting/queries/{qa_hunting_query['id']}/execute/")
        assert resp.status_code == 200
        body = resp.json()
        assert "count" in body and "results" in body

    def test_execute_as_viewer_forbidden(self, qa_hunting_query, qa_viewer_a_client):
        resp = qa_viewer_a_client.post(f"/api/hunting/queries/{qa_hunting_query['id']}/execute/")
        assert resp.status_code == 403

    def test_results_returns_shape(self, qa_hunting_query, qa_analyst_a_client):
        resp = qa_analyst_a_client.get(f"/api/hunting/queries/{qa_hunting_query['id']}/results/")
        assert resp.status_code == 200
        body = resp.json()
        assert "count" in body and "results" in body


class TestHuntRun:
    def test_requires_auth(self, anon_client):
        resp = anon_client.post("/api/hunting/run/", json={"params": {}})
        assert resp.status_code == 401

    def test_as_viewer_forbidden(self, qa_viewer_a_client):
        resp = qa_viewer_a_client.post("/api/hunting/run/", json={"params": {}})
        assert resp.status_code == 403

    def test_as_analyst_returns_results(self, qa_analyst_a_client):
        resp = qa_analyst_a_client.post(
            "/api/hunting/run/", json={"params": {"severity": "low"}, "limit": 10}
        )
        assert resp.status_code == 200
        body = resp.json()
        assert "count" in body and "results" in body and "returned" in body

    def test_disallowed_field_is_silently_ignored(self, qa_analyst_a_client):
        """
        ALLOWED_FIELDS filtre les clés acceptées côté serveur — un champ hors
        liste (ex: `__class__`) ne doit jamais lever d'exception 500.
        """
        resp = qa_analyst_a_client.post(
            "/api/hunting/run/", json={"params": {"not_a_real_field": "x"}, "limit": 5}
        )
        assert resp.status_code == 200
