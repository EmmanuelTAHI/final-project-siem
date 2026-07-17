"""
Tests d'audit prod — apps.ml.
Lecture seule sur models/predictions. train est un POST coûteux (Celery
Isolation Forest) : on vérifie juste que l'endpoint accepte la requête
(202) sans jamais attendre la fin du job ni interroger son statut en boucle.
"""
import uuid


class TestMLModels:
    def test_list_requires_auth(self, anon_client):
        resp = anon_client.get("/api/ml/models/")
        assert resp.status_code == 401

    def test_list_as_analyst_allowed(self, qa_analyst_a_client):
        resp = qa_analyst_a_client.get("/api/ml/models/")
        assert resp.status_code == 200
        assert resp.json()["status"] == "success"

    def test_list_as_viewer_forbidden(self, qa_viewer_a_client):
        resp = qa_viewer_a_client.get("/api/ml/models/")
        assert resp.status_code == 403

    def test_retrieve_unknown_id_returns_404(self, qa_analyst_a_client):
        resp = qa_analyst_a_client.get(f"/api/ml/models/{uuid.uuid4()}/")
        assert resp.status_code == 404


class TestMLPredictions:
    def test_list_requires_auth(self, anon_client):
        resp = anon_client.get("/api/ml/predictions/")
        assert resp.status_code == 401

    def test_list_as_analyst_allowed(self, qa_analyst_a_client):
        resp = qa_analyst_a_client.get("/api/ml/predictions/")
        assert resp.status_code == 200

    def test_list_as_viewer_forbidden(self, qa_viewer_a_client):
        resp = qa_viewer_a_client.get("/api/ml/predictions/")
        assert resp.status_code == 403

    def test_filter_is_anomaly_does_not_error(self, qa_analyst_a_client):
        resp = qa_analyst_a_client.get("/api/ml/predictions/", params={"is_anomaly": "true"})
        assert resp.status_code == 200


class TestMLTrain:
    def test_train_requires_auth(self, anon_client):
        resp = anon_client.post("/api/ml/train/", json={})
        assert resp.status_code == 401

    def test_train_as_viewer_forbidden(self, qa_viewer_a_client):
        resp = qa_viewer_a_client.post("/api/ml/train/", json={})
        assert resp.status_code == 403

    def test_train_as_analyst_accepted(self, qa_analyst_a_client):
        """
        Ne fait QUE vérifier que le job est accepté et mis en queue (202) —
        n'attend jamais la fin de l'entraînement (potentiellement long/coûteux
        en vraie prod).
        """
        resp = qa_analyst_a_client.post(
            "/api/ml/train/", json={"days_of_data": 7, "contamination": 0.05}
        )
        assert resp.status_code == 202
        data = resp.json()["data"]
        assert data["status"] == "pending"
        assert "task_id" in data

    def test_train_invalid_params_returns_400(self, qa_analyst_a_client):
        resp = qa_analyst_a_client.post(
            "/api/ml/train/", json={"days_of_data": 999, "contamination": 5}
        )
        assert resp.status_code == 400

    def test_train_status_unknown_task_does_not_error(self, qa_analyst_a_client):
        resp = qa_analyst_a_client.get(f"/api/ml/train/{uuid.uuid4()}/status/")
        assert resp.status_code == 200
        assert resp.json()["data"]["status"] == "PENDING"
