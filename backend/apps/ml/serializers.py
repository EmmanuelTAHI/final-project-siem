"""
Serializers pour les modèles ML et les prédictions.
"""
from rest_framework import serializers

from .models import MLModel, Prediction


class MLModelSerializer(serializers.ModelSerializer):
    class Meta:
        model = MLModel
        fields = [
            "id",
            "name",
            "version",
            "algorithm",
            "trained_at",
            "accuracy_score",
            "f1_score",
            "is_active",
            "training_samples",
            "contamination_rate",
            "created_at",
        ]
        read_only_fields = fields


class PredictionSerializer(serializers.ModelSerializer):
    model_version = serializers.CharField(source="model.version", read_only=True, allow_null=True)
    log_action = serializers.CharField(source="log.action", read_only=True)
    log_user_email = serializers.CharField(source="log.user_email", read_only=True, allow_null=True)
    log_event_time = serializers.DateTimeField(source="log.event_time", read_only=True)

    class Meta:
        model = Prediction
        fields = [
            "id",
            "log",
            "log_action",
            "log_user_email",
            "log_event_time",
            "model",
            "model_version",
            "is_anomaly",
            "anomaly_score",
            "predicted_at",
        ]
        read_only_fields = fields


class TrainRequestSerializer(serializers.Serializer):
    """Serializer pour la requête de démarrage d'entraînement."""

    days_of_data = serializers.IntegerField(
        min_value=7,
        max_value=365,
        default=30,
        help_text="Nombre de jours de données à utiliser (7-365).",
    )
    contamination = serializers.FloatField(
        min_value=0.01,
        max_value=0.5,
        default=0.05,
        help_text="Proportion estimée d'anomalies dans les données (0.01-0.5).",
    )
