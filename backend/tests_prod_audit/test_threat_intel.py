"""
Tests d'audit prod — apps.threat_intel.
indicators/enriched-logs/stats : lecture seule. Note : CTIStatsView et
l'action lookup() renvoient un `Response(...)` DRF brut (pas le format
standardisé {status, data, message} des autres apps) — les assertions en
tiennent compte.
"""
import uuid


class TestThreatIndicators:
    def test_list_requires_auth(self, anon_client):
        resp = anon_client.get("/api/threat-intel/indicators/")
        assert resp.status_code == 401

    def test_list_as_analyst_allowed(self, qa_analyst_a_client):
        resp = qa_analyst_a_client.get("/api/threat-intel/indicators/")
        assert resp.status_code == 200

    def test_list_as_viewer_forbidden(self, qa_viewer_a_client):
        resp = qa_viewer_a_client.get("/api/threat-intel/indicators/")
        assert resp.status_code == 403

    def test_retrieve_unknown_id_returns_404(self, qa_analyst_a_client):
        resp = qa_analyst_a_client.get(f"/api/threat-intel/indicators/{uuid.uuid4()}/")
        assert resp.status_code == 404

    def test_lookup_ip_returns_verdict(self, qa_analyst_a_client):
        """
        Lookup manuel sur une IP documentaire (TEST-NET-1, RFC 5737) — ne
        touche aucune vraie infrastructure, juste les services d'enrichissement
        (geo/reputation interne, + API externes si configurées).
        """
        resp = qa_analyst_a_client.post(
            "/api/threat-intel/indicators/lookup/",
            json={"value": "192.0.2.1", "type": "ip"},
        )
        assert resp.status_code == 200
        body = resp.json()
        assert body["value"] == "192.0.2.1"
        assert "verdict" in body
        assert body["verdict"]["level"] in ("malicious", "suspicious", "clean", "unknown")

    def test_lookup_missing_value_returns_400(self, qa_analyst_a_client):
        resp = qa_analyst_a_client.post("/api/threat-intel/indicators/lookup/", json={"type": "ip"})
        assert resp.status_code == 400

    def test_lookup_as_viewer_forbidden(self, qa_viewer_a_client):
        resp = qa_viewer_a_client.post(
            "/api/threat-intel/indicators/lookup/", json={"value": "192.0.2.1", "type": "ip"}
        )
        assert resp.status_code == 403


class TestEnrichedLogs:
    def test_list_requires_auth(self, anon_client):
        resp = anon_client.get("/api/threat-intel/enriched-logs/")
        assert resp.status_code == 401

    def test_list_as_analyst_allowed(self, qa_analyst_a_client):
        resp = qa_analyst_a_client.get("/api/threat-intel/enriched-logs/")
        assert resp.status_code == 200

    def test_list_as_viewer_forbidden(self, qa_viewer_a_client):
        resp = qa_viewer_a_client.get("/api/threat-intel/enriched-logs/")
        assert resp.status_code == 403

    def test_filter_is_threat_does_not_error(self, qa_analyst_a_client):
        resp = qa_analyst_a_client.get("/api/threat-intel/enriched-logs/", params={"is_threat": "true"})
        assert resp.status_code == 200


class TestCTIStats:
    def test_requires_auth(self, anon_client):
        resp = anon_client.get("/api/threat-intel/stats/")
        assert resp.status_code == 401

    def test_as_analyst_allowed(self, qa_analyst_a_client):
        resp = qa_analyst_a_client.get("/api/threat-intel/stats/")
        assert resp.status_code == 200
        body = resp.json()
        for key in ("total_indicators", "malicious_indicators", "threats_24h", "by_source", "by_type"):
            assert key in body

    def test_as_viewer_forbidden(self, qa_viewer_a_client):
        resp = qa_viewer_a_client.get("/api/threat-intel/stats/")
        assert resp.status_code == 403
