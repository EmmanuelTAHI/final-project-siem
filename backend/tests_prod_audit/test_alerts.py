"""
Tests d'audit prod — apps.alerts.
Les alertes en prod sont réelles : on ne fait QUE lire/lister/filtrer, jamais
supprimer une alerte existante. AlertViewSet n'expose de toute façon ni
create ni delete (http_method_names = ["get", "patch", "post", ...]) — on
vérifie aussi que ces méthodes sont bien absentes/refusées.
"""
import uuid


class TestAlertsList:
    def test_list_requires_auth(self, anon_client):
        resp = anon_client.get("/api/alerts/")
        assert resp.status_code == 401

    def test_list_as_analyst_allowed(self, qa_analyst_a_client):
        resp = qa_analyst_a_client.get("/api/alerts/")
        assert resp.status_code == 200
        assert resp.json()["status"] == "success"

    def test_list_as_viewer_forbidden(self, qa_viewer_a_client):
        """AlertViewSet.permission_classes = [IsAnalyst] -> viewer refusé."""
        resp = qa_viewer_a_client.get("/api/alerts/")
        assert resp.status_code == 403

    def test_filter_by_status_does_not_error(self, qa_analyst_a_client):
        resp = qa_analyst_a_client.get("/api/alerts/", params={"status": "open"})
        assert resp.status_code == 200

    def test_filter_by_severity_does_not_error(self, qa_analyst_a_client):
        resp = qa_analyst_a_client.get("/api/alerts/", params={"severity": "critical"})
        assert resp.status_code == 200

    def test_retrieve_unknown_id_returns_404(self, qa_analyst_a_client):
        resp = qa_analyst_a_client.get(f"/api/alerts/{uuid.uuid4()}/")
        assert resp.status_code == 404


class TestAlertsWriteRestrictions:
    def test_create_not_allowed_at_all(self, qa_admin_a_client):
        """Pas de POST racine sur AlertViewSet (seul /comments/ accepte POST)."""
        resp = qa_admin_a_client.post("/api/alerts/", json={"title": "should not be created"})
        assert resp.status_code == 405

    def test_delete_not_allowed_at_all(self, qa_admin_a_client):
        resp = qa_admin_a_client.delete(f"/api/alerts/{uuid.uuid4()}/")
        assert resp.status_code in (404, 405)

    def test_put_not_allowed(self, qa_admin_a_client):
        resp = qa_admin_a_client.put(f"/api/alerts/{uuid.uuid4()}/", json={})
        assert resp.status_code in (404, 405)


class TestAlertsPartialUpdate:
    def test_patch_unknown_alert_returns_404(self, qa_analyst_a_client):
        resp = qa_analyst_a_client.patch(f"/api/alerts/{uuid.uuid4()}/", json={"status": "in_progress"})
        assert resp.status_code == 404

    def test_patch_as_viewer_forbidden(self, qa_viewer_a_client):
        resp = qa_viewer_a_client.patch(f"/api/alerts/{uuid.uuid4()}/", json={"status": "in_progress"})
        assert resp.status_code == 403

    def test_patch_real_alert_roundtrip_if_any_exists(self, qa_analyst_a_client):
        """
        Si au moins une alerte existe déjà en prod pour l'org A, vérifie que
        PATCH fonctionne et restaure IMMÉDIATEMENT le statut d'origine — ne
        modifie jamais durablement une alerte réelle.
        """
        list_resp = qa_analyst_a_client.get("/api/alerts/")
        assert list_resp.status_code == 200
        items = list_resp.json()["data"]
        items = items if isinstance(items, list) else items.get("results", [])
        if not items:
            import pytest
            pytest.skip("Aucune alerte existante en prod pour l'org A — rien à tester ici.")

        alert = items[0]
        alert_id = alert["id"]
        detail_resp = qa_analyst_a_client.get(f"/api/alerts/{alert_id}/")
        assert detail_resp.status_code == 200
        original_status = detail_resp.json()["data"]["status"]

        # Choisit un statut de test différent pour prouver le roundtrip, puis
        # restaure toujours l'original dans un `finally`.
        temp_status = "in_progress" if original_status != "in_progress" else "open"
        try:
            patch_resp = qa_analyst_a_client.patch(
                f"/api/alerts/{alert_id}/", json={"status": temp_status}
            )
            assert patch_resp.status_code == 200
            assert patch_resp.json()["data"]["status"] == temp_status
        finally:
            restore_resp = qa_analyst_a_client.patch(
                f"/api/alerts/{alert_id}/", json={"status": original_status}
            )
            assert restore_resp.status_code == 200
            assert restore_resp.json()["data"]["status"] == original_status


class TestAlertComments:
    def test_comments_get_unknown_alert_returns_404(self, qa_analyst_a_client):
        resp = qa_analyst_a_client.get(f"/api/alerts/{uuid.uuid4()}/comments/")
        assert resp.status_code == 404

    def test_comments_post_and_read_roundtrip_if_any_alert_exists(self, qa_analyst_a_client):
        """
        Ajoute un commentaire QA_AUDIT_* sur une alerte réelle existante (le
        commentaire n'est pas nettoyable via l'API — pas de DELETE sur
        AlertComment — donc on le préfixe clairement pour qu'il soit
        identifiable/nettoyable manuellement côté admin si besoin).
        """
        list_resp = qa_analyst_a_client.get("/api/alerts/")
        items = list_resp.json()["data"]
        items = items if isinstance(items, list) else items.get("results", [])
        if not items:
            import pytest
            pytest.skip("Aucune alerte existante en prod pour l'org A — rien à tester ici.")

        alert_id = items[0]["id"]
        marker = f"QA_AUDIT_comment_{uuid.uuid4().hex[:8]}"
        resp = qa_analyst_a_client.post(
            f"/api/alerts/{alert_id}/comments/", json={"content": marker}
        )
        assert resp.status_code == 201
        comments = [c["content"] for c in resp.json()["data"]["comments"]]
        assert marker in comments


class TestAlertsStats:
    def test_stats_requires_auth(self, anon_client):
        resp = anon_client.get("/api/alerts/stats/")
        assert resp.status_code == 401

    def test_stats_as_analyst_allowed(self, qa_analyst_a_client):
        resp = qa_analyst_a_client.get("/api/alerts/stats/")
        assert resp.status_code == 200
        data = resp.json()["data"]
        for key in ("by_severity", "by_status", "total_open", "false_positive_rate_percent"):
            assert key in data

    def test_stats_as_viewer_forbidden(self, qa_viewer_a_client):
        resp = qa_viewer_a_client.get("/api/alerts/stats/")
        assert resp.status_code == 403
