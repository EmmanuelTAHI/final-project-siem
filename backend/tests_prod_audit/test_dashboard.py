"""
Tests d'audit prod — apps.dashboard.
summary/timeline/top-threats/geo-map : lecture seule, IsAuthenticated (tous
rôles), vérifie 200 + shape JSON basique.
"""


class TestDashboardSummary:
    def test_requires_auth(self, anon_client):
        resp = anon_client.get("/api/dashboard/summary/")
        assert resp.status_code == 401

    def test_viewer_can_read(self, qa_viewer_a_client):
        resp = qa_viewer_a_client.get("/api/dashboard/summary/")
        assert resp.status_code == 200
        data = resp.json()["data"]
        for key in ("alerts", "logs", "connectors", "ml", "generated_at"):
            assert key in data
        assert "total_open" in data["alerts"]


class TestDashboardTimeline:
    def test_requires_auth(self, anon_client):
        resp = anon_client.get("/api/dashboard/timeline/")
        assert resp.status_code == 401

    def test_default_period(self, qa_viewer_a_client):
        resp = qa_viewer_a_client.get("/api/dashboard/timeline/")
        assert resp.status_code == 200
        data = resp.json()["data"]
        assert data["period"] == "24h"
        assert "logs" in data and "alerts" in data

    def test_period_7d(self, qa_viewer_a_client):
        resp = qa_viewer_a_client.get("/api/dashboard/timeline/", params={"period": "7d"})
        assert resp.status_code == 200
        assert resp.json()["data"]["period"] == "7d"

    def test_period_30d(self, qa_viewer_a_client):
        resp = qa_viewer_a_client.get("/api/dashboard/timeline/", params={"period": "30d"})
        assert resp.status_code == 200
        assert resp.json()["data"]["period"] == "30d"

    def test_invalid_period_falls_back_to_24h(self, qa_viewer_a_client):
        resp = qa_viewer_a_client.get("/api/dashboard/timeline/", params={"period": "bogus"})
        assert resp.status_code == 200
        assert resp.json()["data"]["period"] == "24h"


class TestDashboardTopThreats:
    def test_requires_auth(self, anon_client):
        resp = anon_client.get("/api/dashboard/top-threats/")
        assert resp.status_code == 401

    def test_viewer_can_read(self, qa_viewer_a_client):
        resp = qa_viewer_a_client.get("/api/dashboard/top-threats/")
        assert resp.status_code == 200
        assert "top_threats" in resp.json()["data"]
        assert isinstance(resp.json()["data"]["top_threats"], list)


class TestDashboardGeoMap:
    def test_requires_auth(self, anon_client):
        resp = anon_client.get("/api/dashboard/geo-map/")
        assert resp.status_code == 401

    def test_viewer_can_read(self, qa_viewer_a_client):
        resp = qa_viewer_a_client.get("/api/dashboard/geo-map/")
        assert resp.status_code == 200
        data = resp.json()["data"]
        assert data["period"] == "24h"
        assert "countries" in data
