"""
Modèles du module Machine Learning.
MLModel : métadonnées du modèle entraîné.
Prediction : résultat de l'inférence sur un log.
"""
import uuid

from django.db import models


class MLModel(models.Model):
    """
    Modèle ML entraîné et sauvegardé.
    Le fichier du modèle est stocké avec joblib.
    """

    ALGORITHM_CHOICES = [
        ("isolation_forest", "Isolation Forest"),
        ("autoencoder", "Autoencoder"),
        ("local_outlier_factor", "Local Outlier Factor"),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    organization = models.ForeignKey(
        "organizations.Organization",
        on_delete=models.CASCADE,
        related_name="ml_models",
        verbose_name="Organisation",
        help_text="Chaque organisation entraîne son propre modèle sur son propre corpus de logs.",
    )
    name = models.CharField(max_length=255, verbose_name="Nom du modèle")
    version = models.CharField(max_length=50, verbose_name="Version", help_text="Ex: 1.0.0")
    algorithm = models.CharField(
        max_length=50,
        choices=ALGORITHM_CHOICES,
        default="isolation_forest",
        verbose_name="Algorithme",
    )
    trained_at = models.DateTimeField(null=True, blank=True, verbose_name="Entraîné le")
    accuracy_score = models.FloatField(null=True, blank=True, verbose_name="Score de précision")
    f1_score = models.FloatField(null=True, blank=True, verbose_name="F1-Score")
    is_active = models.BooleanField(default=False, verbose_name="Actif")
    model_file = models.FileField(
        upload_to="ml_models/",
        verbose_name="Fichier du modèle",
    )
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="Créé le")
    training_samples = models.IntegerField(default=0, verbose_name="Échantillons d'entraînement")
    contamination_rate = models.FloatField(default=0.05, verbose_name="Taux de contamination")

    class Meta:
        verbose_name = "Modèle ML"
        verbose_name_plural = "Modèles ML"
        ordering = ["-created_at"]

    def __str__(self):
        active = "✓ ACTIF" if self.is_active else "✗"
        return f"{self.name} v{self.version} [{self.algorithm}] {active}"

    def activate(self):
        """Active ce modèle et désactive les autres modèles de la même organisation."""
        MLModel.objects.filter(
            organization_id=self.organization_id, is_active=True
        ).exclude(pk=self.pk).update(is_active=False)
        self.is_active = True
        self.save(update_fields=["is_active"])


class Prediction(models.Model):
    """
    Résultat de l'inférence ML sur un log normalisé.
    """

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    organization = models.ForeignKey(
        "organizations.Organization",
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name="predictions",
        verbose_name="Organisation",
        help_text="Dénormalisé depuis log.organization pour l'isolation multi-tenant.",
    )
    log = models.OneToOneField(
        "logs.NormalizedLog",
        on_delete=models.CASCADE,
        related_name="prediction",
        verbose_name="Log analysé",
    )
    model = models.ForeignKey(
        MLModel,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="predictions",
        verbose_name="Modèle utilisé",
    )
    is_anomaly = models.BooleanField(verbose_name="Anomalie détectée", db_index=True)
    anomaly_score = models.FloatField(
        verbose_name="Score d'anomalie",
        help_text="Plus le score est élevé, plus l'événement est anormal (0.0 à 1.0).",
    )
    predicted_at = models.DateTimeField(auto_now_add=True, verbose_name="Prédit le")

    class Meta:
        verbose_name = "Prédiction ML"
        verbose_name_plural = "Prédictions ML"
        ordering = ["-predicted_at"]
        indexes = [
            models.Index(fields=["is_anomaly", "predicted_at"]),
            models.Index(fields=["anomaly_score"]),
        ]

    def save(self, *args, **kwargs):
        if self.log_id and not self.organization_id:
            self.organization_id = self.log.organization_id
        super().save(*args, **kwargs)

    def __str__(self):
        flag = "⚠ ANOMALIE" if self.is_anomaly else "✓ Normal"
        return f"{flag} — score={self.anomaly_score:.3f} — log={self.log_id}"
