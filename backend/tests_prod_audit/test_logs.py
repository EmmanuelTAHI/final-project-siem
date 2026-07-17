"""
Tests d'audit prod — apps.logs.
Lecture seule (RawLog/NormalizedLog en ReadOnlyModelViewSet) : vérifie 200 en
lecture, 403 en écriture/suppression pour les rôles insuffisants, et 405 pour
les méthodes non supportées par le ViewSet (POST/DELETE/PUT).
"""
import uuid


class TestRawLogs:
    def test_list_requires_auth(self, anon_client):
        resp = anon_client.get("/api/logs/raw/")
        assert resp.status_code == 401

    def test_list_as_analyst_allowed(self, qa_analyst_a_client):
        resp = qa_analyst_a_client.get("/api/logs/raw/")
        assert resp.status_code == 200
        assert resp.json()["status"] == "success"

    def test_list_as_viewer_forbidden(self, qa_viewer_a_client):
        """RawLogViewSet.permission_classes = [IsAnalyst] -> viewer refusé."""
        resp = qa_viewer_a_client.get("/api/logs/raw/")
        assert resp.status_code == 403

    def test_post_not_allowed(self, qa_analyst_a_client):
        resp = qa_analyst_a_client.post("/api/logs/raw/", json={"foo": "bar"})
        assert resp.status_code == 405

    def test_delete_not_allowed(self, qa_analyst_a_client):
        resp = qa_analyst_a_client.delete(f"/api/logs/raw/{uuid.uuid4()}/")
        assert resp.status_code in (404, 405)

    def test_retrieve_unknown_id_returns_404(self, qa_analyst_a_client):
        resp = qa_analyst_a_client.get(f"/api/logs/raw/{uuid.uuid4()}/")
        assert resp.status_code == 404


class TestNormalizedLogs:
    def test_list_requires_auth(self, anon_client):
        resp = anon_client.get("/api/logs/normalized/")
        assert resp.status_code == 401

    def test_list_as_analyst_allowed(self, qa_analyst_a_client):
        resp = qa_analyst_a_client.get("/api/logs/normalized/")
        assert resp.status_code == 200
        assert resp.json()["status"] == "success"

    def test_list_as_viewer_forbidden(self, qa_viewer_a_client):
        resp = qa_viewer_a_client.get("/api/logs/normalized/")
        assert resp.status_code == 403

    def test_post_not_allowed(self, qa_analyst_a_client):
        resp = qa_analyst_a_client.post("/api/logs/normalized/", json={"foo": "bar"})
        assert resp.status_code == 405

    def test_search_filter_does_not_error(self, qa_analyst_a_client):
        resp = qa_analyst_a_client.get("/api/logs/normalized/", params={"search": "test"})
        assert resp.status_code == 200


class TestLogStats:
    def test_stats_requires_auth(self, anon_client):
        resp = anon_client.get("/api/logs/stats/")
        assert resp.status_code == 401

    def test_stats_as_analyst_allowed(self, qa_analyst_a_client):
        resp = qa_analyst_a_client.get("/api/logs/stats/")
        assert resp.status_code == 200
        data = resp.json()["data"]
        for key in (
            "hourly_volume_24h", "daily_volume_30d", "top_source_ips",
            "top_users", "by_action", "by_country",
        ):
            assert key in data

    def test_stats_as_viewer_forbidden(self, qa_viewer_a_client):
        resp = qa_viewer_a_client.get("/api/logs/stats/")
        assert resp.status_code == 403
