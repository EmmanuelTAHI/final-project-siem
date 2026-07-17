"""
Tests d'audit prod — apps.organizations (routes /api/platform/).
Réservé au staff plateforme (superuser) — IsPlatformStaff. QA_ADMIN_A/B sont
admin de leur ORG mais PAS superuser plateforme -> doivent recevoir 403.
Seul ADMIN (superuser réel) doit pouvoir lister toutes les organisations.
"""
import uuid


class TestPlatformOrganizations:
    def test_requires_auth(self, anon_client):
        resp = anon_client.get("/api/platform/organizations/")
        assert resp.status_code == 401

    def test_qa_admin_a_forbidden(self, qa_admin_a_client):
        """QA_ADMIN_A est admin d'org, pas superuser plateforme."""
        resp = qa_admin_a_client.get("/api/platform/organizations/")
        assert resp.status_code == 403

    def test_qa_admin_b_forbidden(self, qa_admin_b_client):
        resp = qa_admin_b_client.get("/api/platform/organizations/")
        assert resp.status_code == 403

    def test_qa_analyst_a_forbidden(self, qa_analyst_a_client):
        resp = qa_analyst_a_client.get("/api/platform/organizations/")
        assert resp.status_code == 403

    def test_admin_superuser_allowed(self, admin_client):
        """ADMIN est le superuser plateforme réel — accès cross-org attendu."""
        resp = admin_client.get("/api/platform/organizations/")
        assert resp.status_code == 200
        body = resp.json()
        assert body["status"] == "success"

    def test_admin_can_see_both_qa_orgs(self, admin_client):
        """
        Vérifie que la vue cross-org voit bien AU MOINS les deux organisations
        QA utilisées par cette suite (Log+ (Legacy) et QA Test Org B) —
        confirme que allow_cross_org_for_platform_staff fonctionne réellement.
        """
        resp = admin_client.get("/api/platform/organizations/")
        assert resp.status_code == 200
        items = resp.json()["data"]
        items = items if isinstance(items, list) else items.get("results", [])
        names = {org["name"] for org in items}
        assert any("legacy" in n.lower() or "log+" in n.lower() for n in names)
        assert any("qa test org b" in n.lower() for n in names)

    def test_stats_action_requires_platform_staff(self, qa_admin_a_client):
        resp = qa_admin_a_client.get(f"/api/platform/organizations/{uuid.uuid4()}/stats/")
        assert resp.status_code == 403

    def test_stats_action_as_admin_returns_shape(self, admin_client):
        list_resp = admin_client.get("/api/platform/organizations/")
        items = list_resp.json()["data"]
        items = items if isinstance(items, list) else items.get("results", [])
        assert items, "Aucune organisation trouvée — impossible de tester /stats/."
        org_id = items[0]["id"]
        resp = admin_client.get(f"/api/platform/organizations/{org_id}/stats/")
        assert resp.status_code == 200
        data = resp.json()["data"]
        for key in ("user_count", "connector_count", "log_count", "open_alert_count"):
            assert key in data

    def test_overview_requires_platform_staff(self, qa_admin_a_client):
        resp = qa_admin_a_client.get("/api/platform/organizations/overview/")
        assert resp.status_code == 403

    def test_overview_as_admin_returns_shape(self, admin_client):
        resp = admin_client.get("/api/platform/organizations/overview/")
        assert resp.status_code == 200
        data = resp.json()["data"]
        for key in ("organization_count", "active_organization_count", "total_user_count"):
            assert key in data
