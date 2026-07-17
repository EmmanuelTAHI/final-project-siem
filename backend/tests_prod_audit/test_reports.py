"""
Tests d'audit prod — apps.reports.
compliance/frameworks (lecture), generate (POST-like via GET, vérifie
juste que ça répond sans télécharger en boucle), export, history.
Ces endpoints génèrent de vrais PDF/CSV (potentiellement coûteux) : on ne
les appelle qu'une fois chacun, avec une période courte, jamais en boucle.
"""


class TestFrameworks:
    def test_requires_auth(self, anon_client):
        resp = anon_client.get("/api/reports/frameworks/")
        assert resp.status_code == 401

    def test_as_analyst_allowed(self, qa_analyst_a_client):
        resp = qa_analyst_a_client.get("/api/reports/frameworks/")
        assert resp.status_code == 200
        body = resp.json()
        assert isinstance(body, list)
        assert any(item["id"] == "pci_dss" for item in body)

    def test_as_viewer_forbidden(self, qa_viewer_a_client):
        resp = qa_viewer_a_client.get("/api/reports/frameworks/")
        assert resp.status_code == 403


class TestComplianceReport:
    def test_requires_auth(self, anon_client):
        resp = anon_client.get("/api/reports/compliance/")
        assert resp.status_code == 401

    def test_unknown_framework_returns_400(self, qa_analyst_a_client):
        resp = qa_analyst_a_client.get(
            "/api/reports/compliance/", params={"framework": "not_a_real_framework"}
        )
        assert resp.status_code == 400

    def test_valid_framework_returns_pdf(self, qa_analyst_a_client):
        """Génère un vrai PDF (une seule fois, période minimale) — vérifie
        juste le content-type, ne parse pas le PDF."""
        resp = qa_analyst_a_client.get(
            "/api/reports/compliance/", params={"framework": "pci_dss", "period": 7}
        )
        assert resp.status_code == 200
        assert resp.headers.get("content-type", "").startswith("application/pdf")

    def test_as_viewer_forbidden(self, qa_viewer_a_client):
        resp = qa_viewer_a_client.get("/api/reports/compliance/")
        assert resp.status_code == 403


class TestReportGenerate:
    def test_requires_auth(self, anon_client):
        resp = anon_client.get("/api/reports/generate/")
        assert resp.status_code == 401

    def test_unknown_type_returns_400(self, qa_analyst_a_client):
        resp = qa_analyst_a_client.get("/api/reports/generate/", params={"type": "not_a_real_type"})
        assert resp.status_code == 400

    def test_soc_weekly_generates_pdf(self, qa_analyst_a_client):
        resp = qa_analyst_a_client.get(
            "/api/reports/generate/", params={"type": "soc_weekly", "period": 7}
        )
        assert resp.status_code == 200
        assert resp.headers.get("content-type", "").startswith("application/pdf")

    def test_as_viewer_forbidden(self, qa_viewer_a_client):
        resp = qa_viewer_a_client.get("/api/reports/generate/", params={"type": "soc_weekly"})
        assert resp.status_code == 403


class TestReportExport:
    def test_requires_auth(self, anon_client):
        resp = anon_client.get("/api/reports/export/")
        assert resp.status_code == 401

    def test_invalid_format_returns_400(self, qa_analyst_a_client):
        resp = qa_analyst_a_client.get("/api/reports/export/", params={"format": "xml"})
        assert resp.status_code == 400

    def test_csv_export_succeeds(self, qa_analyst_a_client):
        resp = qa_analyst_a_client.get(
            "/api/reports/export/", params={"format": "csv", "period": 7}
        )
        assert resp.status_code == 200
        assert resp.headers.get("content-type", "").startswith("text/csv")

    def test_json_export_succeeds(self, qa_analyst_a_client):
        resp = qa_analyst_a_client.get(
            "/api/reports/export/", params={"format": "json", "period": 7}
        )
        assert resp.status_code == 200
        assert resp.headers.get("content-type", "").startswith("application/json")

    def test_as_viewer_forbidden(self, qa_viewer_a_client):
        resp = qa_viewer_a_client.get("/api/reports/export/")
        assert resp.status_code == 403


class TestReportHistory:
    def test_requires_auth(self, anon_client):
        resp = anon_client.get("/api/reports/history/")
        assert resp.status_code == 401

    def test_as_analyst_allowed(self, qa_analyst_a_client):
        """
        Les exports ci-dessus (compliance/generate/export) alimentent déjà
        l'historique via _save_history() — cette liste ne devrait donc jamais
        être vide après les tests précédents dans le même run.
        """
        resp = qa_analyst_a_client.get("/api/reports/history/")
        assert resp.status_code == 200
        assert resp.json()["status"] == "success"

    def test_as_viewer_forbidden(self, qa_viewer_a_client):
        resp = qa_viewer_a_client.get("/api/reports/history/")
        assert resp.status_code == 403
