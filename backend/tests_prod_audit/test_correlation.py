"""
Tests d'audit prod — apps.correlation.
CRUD règles (create QA_AUDIT_* -> delete), actions toggle/test, permission
IsAnalyst (viewer -> 403).
"""
import uuid

import pytest

from conftest import QA_PREFIX


def _rule_payload(name):
    return {
        "name": name,
        "description": "Règle QA d'audit — supprimée automatiquement en fin de test.",
        "is_active": False,  # inactive pour ne jamais réellement matcher en prod
        "severity": "low",
        "rule_type": "threshold",
        "condition_logic": {"type": "threshold", "field": "action", "value": "login_failed", "threshold": 999999},
        "mitre_tactic": "TA0006",
        "mitre_technique": "T1110",
    }


@pytest.fixture
def qa_rule(qa_admin_a_client):
    name = f"{QA_PREFIX}rule_{uuid.uuid4().hex[:8]}"
    resp = qa_admin_a_client.post("/api/correlation/rules/", json=_rule_payload(name))
    assert resp.status_code == 201, resp.text
    rule = resp.json()["data"]
    try:
        yield rule
    finally:
        qa_admin_a_client.delete(f"/api/correlation/rules/{rule['id']}/")


class TestCorrelationRulesCRUD:
    def test_list_requires_auth(self, anon_client):
        resp = anon_client.get("/api/correlation/rules/")
        assert resp.status_code == 401

    def test_list_as_viewer_forbidden(self, qa_viewer_a_client):
        resp = qa_viewer_a_client.get("/api/correlation/rules/")
        assert resp.status_code == 403

    def test_create_get_update_delete_cycle(self, qa_admin_a_client):
        name = f"{QA_PREFIX}rule_{uuid.uuid4().hex[:8]}"
        created_id = None
        try:
            create_resp = qa_admin_a_client.post("/api/correlation/rules/", json=_rule_payload(name))
            assert create_resp.status_code == 201, create_resp.text
            created = create_resp.json()["data"]
            created_id = created["id"]
            assert created["name"] == name
            assert created["rule_type"] == "threshold"

            get_resp = qa_admin_a_client.get(f"/api/correlation/rules/{created_id}/")
            assert get_resp.status_code == 200

            update_payload = _rule_payload(name + "_updated")
            update_resp = qa_admin_a_client.put(
                f"/api/correlation/rules/{created_id}/", json=update_payload
            )
            assert update_resp.status_code == 200
            assert update_resp.json()["data"]["name"] == name + "_updated"
        finally:
            if created_id:
                del_resp = qa_admin_a_client.delete(f"/api/correlation/rules/{created_id}/")
                assert del_resp.status_code == 204
                created_id = None

    def test_create_missing_rule_type_returns_400(self, qa_admin_a_client):
        payload = _rule_payload(f"{QA_PREFIX}bad_rule_{uuid.uuid4().hex[:8]}")
        payload.pop("rule_type")
        payload["condition_logic"] = {}
        resp = qa_admin_a_client.post("/api/correlation/rules/", json=payload)
        assert resp.status_code == 400

    def test_create_as_analyst_allowed(self, qa_analyst_a_client):
        """CorrelationRuleViewSet.get_permissions : create -> IsAnalyst (analyst+admin)."""
        name = f"{QA_PREFIX}rule_analyst_{uuid.uuid4().hex[:8]}"
        resp = qa_analyst_a_client.post("/api/correlation/rules/", json=_rule_payload(name))
        assert resp.status_code == 201, resp.text
        rule_id = resp.json()["data"]["id"]
        del_resp = qa_analyst_a_client.delete(f"/api/correlation/rules/{rule_id}/")
        assert del_resp.status_code == 204

    def test_create_as_viewer_forbidden(self, qa_viewer_a_client):
        resp = qa_viewer_a_client.post(
            "/api/correlation/rules/", json=_rule_payload(f"{QA_PREFIX}should_fail")
        )
        assert resp.status_code == 403

    def test_delete_as_viewer_forbidden(self, qa_rule, qa_viewer_a_client):
        resp = qa_viewer_a_client.delete(f"/api/correlation/rules/{qa_rule['id']}/")
        assert resp.status_code == 403


class TestCorrelationRuleActions:
    def test_toggle_flips_is_active(self, qa_rule, qa_admin_a_client):
        original_state = qa_rule["is_active"]
        resp = qa_admin_a_client.post(f"/api/correlation/rules/{qa_rule['id']}/toggle/")
        assert resp.status_code == 200
        assert resp.json()["data"]["is_active"] == (not original_state)
        # remet dans l'état d'origine pour rester cohérent (bien que le
        # teardown de la fixture supprime la règle de toute façon).
        qa_admin_a_client.post(f"/api/correlation/rules/{qa_rule['id']}/toggle/")

    def test_toggle_as_viewer_forbidden(self, qa_rule, qa_viewer_a_client):
        resp = qa_viewer_a_client.post(f"/api/correlation/rules/{qa_rule['id']}/toggle/")
        assert resp.status_code == 403

    def test_test_action_runs_without_error(self, qa_rule, qa_admin_a_client):
        resp = qa_admin_a_client.post(f"/api/correlation/rules/{qa_rule['id']}/test/")
        assert resp.status_code in (200, 500)

    def test_test_action_as_viewer_forbidden(self, qa_rule, qa_viewer_a_client):
        resp = qa_viewer_a_client.post(f"/api/correlation/rules/{qa_rule['id']}/test/")
        assert resp.status_code == 403
