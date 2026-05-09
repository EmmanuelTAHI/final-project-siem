"""
Détecteur d'anomalies basé sur Isolation Forest (scikit-learn).
Réf. : Islam 2023, Tendikov et al. 2024
"""
import logging
import os
from datetime import timedelta
from pathlib import Path

import joblib
import numpy as np
from django.conf import settings
from django.utils import timezone
from sklearn.ensemble import IsolationForest
from sklearn.preprocessing import StandardScaler

from .feature_extractor import FeatureExtractor

logger = logging.getLogger(__name__)

ANOMALY_ALERT_THRESHOLD = 0.7


class AnomalyDetector:
    """
    Encapsule le cycle d'entraînement et d'inférence du modèle Isolation Forest.
    """

    def __init__(self):
        self.model: IsolationForest | None = None
        self.scaler: StandardScaler | None = None
        self.extractor: FeatureExtractor | None = None

    def train(
        self,
        days_of_data: int = 30,
        contamination: float = 0.05,
        n_estimators: int = 100,
    ) -> dict:
        """
        Entraîne le modèle Isolation Forest sur les NormalizedLog récents.

        Args:
            days_of_data: Nombre de jours d'historique à utiliser.
            contamination: Proportion estimée d'anomalies (0 < x < 0.5).
            n_estimators: Nombre d'arbres dans la forêt.

        Returns:
            Dictionnaire avec les métriques d'entraînement.
        """
        from apps.logs.models import NormalizedLog

        since = timezone.now() - timedelta(days=days_of_data)
        train_qs = NormalizedLog.objects.filter(event_time__gte=since)
        train_count = train_qs.count()

        if train_count < 50:
            raise ValueError(
                f"Données insuffisantes pour l'entraînement : {train_count} logs "
                f"(minimum requis : 50). Augmentez 'days_of_data' ou attendez plus de données."
            )

        logger.info("Entraînement IsolationForest sur %d logs (%d jours).", train_count, days_of_data)

        # Préparer les features
        self.extractor = FeatureExtractor()
        df = self.extractor.to_dataframe(train_qs)
        self.extractor.fit(df)
        X, log_ids = self.extractor.transform(train_qs)

        if X.shape[0] == 0:
            raise ValueError("Aucune feature extraite. Vérifiez les données.")

        # Normaliser
        self.scaler = StandardScaler()
        X_scaled = self.scaler.fit_transform(X)

        # Entraîner
        self.model = IsolationForest(
            contamination=contamination,
            n_estimators=n_estimators,
            random_state=42,
            n_jobs=-1,
        )
        self.model.fit(X_scaled)

        # Scores d'anomalie sur les données d'entraînement
        scores = self.model.decision_function(X_scaled)
        anomaly_labels = self.model.predict(X_scaled)
        anomaly_count = int(np.sum(anomaly_labels == -1))

        logger.info(
            "Entraînement terminé : %d anomalies détectées / %d logs (%.1f%%)",
            anomaly_count,
            train_count,
            anomaly_count / train_count * 100,
        )

        return {
            "training_samples": train_count,
            "anomaly_count_training": anomaly_count,
            "anomaly_rate_percent": round(anomaly_count / train_count * 100, 2),
            "contamination": contamination,
            "n_estimators": n_estimators,
            "features_count": X.shape[1],
        }

    def save_model(self, ml_model_instance) -> str:
        """
        Sauvegarde le modèle et le scaler avec joblib.

        Args:
            ml_model_instance: Instance de apps.ml.models.MLModel.

        Returns:
            Chemin du fichier sauvegardé.
        """
        models_dir = Path(settings.ML_MODELS_DIR)
        models_dir.mkdir(parents=True, exist_ok=True)

        filename = f"isolation_forest_{ml_model_instance.version}.joblib"
        filepath = models_dir / filename

        payload = {
            "model": self.model,
            "scaler": self.scaler,
            "extractor": self.extractor,
            "version": ml_model_instance.version,
        }
        joblib.dump(payload, str(filepath))
        logger.info("Modèle sauvegardé : %s", filepath)
        return str(filepath)

    @classmethod
    def load_active_model(cls) -> "AnomalyDetector | None":
        """
        Charge le modèle actif depuis le fichier enregistré dans MLModel.
        """
        from apps.ml.models import MLModel

        try:
            active_ml_model = MLModel.objects.filter(is_active=True).latest("created_at")
        except MLModel.DoesNotExist:
            logger.warning("Aucun modèle ML actif trouvé.")
            return None

        try:
            payload = joblib.load(active_ml_model.model_file.path)
            detector = cls()
            detector.model = payload["model"]
            detector.scaler = payload["scaler"]
            detector.extractor = payload["extractor"]
            logger.info(
                "Modèle ML chargé : %s v%s",
                active_ml_model.name,
                active_ml_model.version,
            )
            return detector
        except Exception as exc:
            logger.exception("Erreur chargement modèle ML : %s", exc)
            return None

    def predict(self, logs_queryset) -> list[dict]:
        """
        Effectue l'inférence sur un QuerySet de NormalizedLog.

        Args:
            logs_queryset: QuerySet de NormalizedLog sans Prediction.

        Returns:
            Liste de dict {log_id, is_anomaly, anomaly_score}.
        """
        if self.model is None or self.scaler is None or self.extractor is None:
            raise ValueError("Le modèle n'est pas chargé. Appelez load_active_model() d'abord.")

        X, log_ids = self.extractor.transform(logs_queryset)

        if X.shape[0] == 0:
            return []

        X_scaled = self.scaler.transform(X)

        # Predict : -1 = anomalie, 1 = normal
        labels = self.model.predict(X_scaled)

        # Score de décision normalisé vers [0, 1]
        # decision_function retourne des valeurs négatives pour les anomalies
        raw_scores = self.model.decision_function(X_scaled)
        # Normaliser : anomalie (négatif) → score élevé
        min_score = raw_scores.min()
        max_score = raw_scores.max()
        if max_score > min_score:
            normalized_scores = 1.0 - (raw_scores - min_score) / (max_score - min_score)
        else:
            normalized_scores = np.zeros_like(raw_scores)

        results = []
        for i, log_id in enumerate(log_ids):
            is_anomaly = bool(labels[i] == -1)
            anomaly_score = float(normalized_scores[i])
            results.append({
                "log_id": log_id,
                "is_anomaly": is_anomaly,
                "anomaly_score": round(anomaly_score, 4),
            })

        return results
