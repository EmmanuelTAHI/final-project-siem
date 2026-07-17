"""
Tests d'audit prod — isolation multi-tenant cross-org.
QA_ADMIN_A (org "Log+ (Legacy)") crée une ressource, QA_ADMIN_B (org "QA Test
Org B") ne doit JAMAIS la voir dans sa liste ni y accéder en direct par id
(404, grâce à OrganizationFilterBackend qui pré-filtre le queryset avant
get_object() -> DoesNotExist -> 404, PAS 403, cf. utils/tenant.py).

Couvre 3 types de ressources : alerts (lecture, on ne crée rien — on vérifie
juste qu'aucune alerte de l'org A n'apparaît côté org B), collectors
(ConnectorConfig créé/détruit par le test) et correlation rules (créé/détruit
par le test). Nettoyage systématique avec le compte A (created_by).
"""
import uuid

from conftest import QA_PREFIX


class TestConnectorIsolation:
    def test_org_b_cannot_see_or_access_org_a_connector(self, qa_admin_a_client, qa_admin_b_client):
        name = f"{QA_PREFIX}ISOLATION_connector_{uuid.uuid4().hex[:8]}"
        create_resp = qa_admin_a_client.post(
            "/api/collectors/connectors/",
            json={"name": name, "source_type": "syslog", "is_active": True},
        )
        assert create_resp.status_code == 201, create_resp.text
        connector_id = create_resp.json()["data"]["id"]
        try:
            # 1. La liste de l'org B ne doit jamais contenir cette ressource.
            list_resp = qa_admin_b_client.get("/api/collectors/connectors/")
            assert list_resp.status_code == 200
            items = list_resp.json()["data"]
            items = items if isinstance(items, list) else items.get("results", [])
            assert not any(c["id"] == connector_id for c in items)

            # 2. Accès direct par id depuis l'org B -> 404 (pas 403 : le
            #    queryset est déjà filtré avant get_object()).
            detail_resp = qa_admin_b_client.get(f"/api/collectors/connectors/{connector_id}/")
            assert detail_resp.status_code == 404

            # 3. L'org B ne doit pas non plus pouvoir le supprimer.
            delete_resp = qa_admin_b_client.delete(f"/api/collectors/connectors/{connector_id}/")
            assert delete_resp.status_code == 404
        finally:
            qa_admin_a_client.delete(f"/api/collectors/connectors/{connector_id}/")


class TestCorrelationRuleIsolation:
    def test_org_b_cannot_see_or_access_org_a_rule(self, qa_admin_a_client, qa_admin_b_client):
        name = f"{QA_PREFIX}ISOLATION_rule_{uuid.uuid4().hex[:8]}"
        create_resp = qa_admin_a_client.post(
            "/api/correlation/rules/",
            json={
                "name": name,
                "is_active": False,
                "severity": "low",
                "rule_type": "threshold",
                "condition_logic": {"type": "threshold", "field": "action", "threshold": 999999},
            },
        )
        assert create_resp.status_code == 201, create_resp.text
        rule_id = create_resp.json()["data"]["id"]
        try:
            list_resp = qa_admin_b_client.get("/api/correlation/rules/")
            assert list_resp.status_code == 200
            items = list_resp.json()["data"]
            items = items if isinstance(items, list) else items.get("results", [])
            assert not any(r["id"] == rule_id for r in items)

            detail_resp = qa_admin_b_client.get(f"/api/correlation/rules/{rule_id}/")
            assert detail_resp.status_code == 404

            delete_resp = qa_admin_b_client.delete(f"/api/correlation/rules/{rule_id}/")
            assert delete_resp.status_code == 404
        finally:
            qa_admin_a_client.delete(f"/api/correlation/rules/{rule_id}/")


class TestAlertIsolation:
    def test_org_b_never_sees_org_a_alerts(self, qa_admin_a_client, qa_admin_b_client):
        """
        Aucune création d'alerte ici (pas de POST exposé sur AlertViewSet) :
        on vérifie plutôt que, si l'org A a des alertes réelles, aucune
        n'apparaît dans la liste de l'org B, et qu'un accès direct par id
        depuis l'org B est un 404.
        """
        list_a = qa_admin_a_client.get("/api/alerts/")
        assert list_a.status_code == 200
        items_a = list_a.json()["data"]
        items_a = items_a if isinstance(items_a, list) else items_a.get("results", [])
        if not items_a:
            import pytest
            pytest.skip("Aucune alerte existante pour l'org A — rien à vérifier ici.")

        alert_id = items_a[0]["id"]

        list_b = qa_admin_b_client.get("/api/alerts/")
        assert list_b.status_code == 200
        items_b = list_b.json()["data"]
        items_b = items_b if isinstance(items_b, list) else items_b.get("results", [])
        assert not any(a["id"] == alert_id for a in items_b)

        detail_b = qa_admin_b_client.get(f"/api/alerts/{alert_id}/")
        assert detail_b.status_code == 404


class TestUserIsolation:
    def test_org_b_admin_cannot_manage_org_a_users(self, qa_admin_a_client, qa_admin_b_client):
        """UserViewSet est aussi filtré par organisation via OrganizationFilterBackend."""
        list_a = qa_admin_a_client.get("/api/users/")
        assert list_a.status_code == 200
        items_a = list_a.json()["data"]
        items_a = items_a if isinstance(items_a, list) else items_a.get("results", [])
        assert items_a, "L'org A devrait avoir au moins les comptes QA."
        user_id = items_a[0]["id"]

        detail_b = qa_admin_b_client.get(f"/api/users/{user_id}/")
        assert detail_b.status_code == 404
