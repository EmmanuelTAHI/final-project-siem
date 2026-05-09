import uuid
import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    initial = True

    dependencies = [
        ("logs", "0001_initial"),
    ]

    operations = [
        migrations.CreateModel(
            name="MLModel",
            fields=[
                ("id", models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ("name", models.CharField(max_length=255, verbose_name="Nom du modèle")),
                ("version", models.CharField(help_text="Ex: 1.0.0", max_length=50, verbose_name="Version")),
                ("algorithm", models.CharField(
                    choices=[
                        ("isolation_forest", "Isolation Forest"),
                        ("autoencoder", "Autoencoder"),
                        ("local_outlier_factor", "Local Outlier Factor"),
                    ],
                    default="isolation_forest",
                    max_length=50,
                    verbose_name="Algorithme",
                )),
                ("trained_at", models.DateTimeField(blank=True, null=True, verbose_name="Entraîné le")),
                ("accuracy_score", models.FloatField(blank=True, null=True, verbose_name="Score de précision")),
                ("f1_score", models.FloatField(blank=True, null=True, verbose_name="F1-Score")),
                ("is_active", models.BooleanField(default=False, verbose_name="Actif")),
                ("model_file", models.FileField(upload_to="ml_models/", verbose_name="Fichier du modèle")),
                ("created_at", models.DateTimeField(auto_now_add=True, verbose_name="Créé le")),
                ("training_samples", models.IntegerField(default=0, verbose_name="Échantillons d'entraînement")),
                ("contamination_rate", models.FloatField(default=0.05, verbose_name="Taux de contamination")),
            ],
            options={
                "verbose_name": "Modèle ML",
                "verbose_name_plural": "Modèles ML",
                "ordering": ["-created_at"],
            },
        ),
        migrations.CreateModel(
            name="Prediction",
            fields=[
                ("id", models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ("is_anomaly", models.BooleanField(db_index=True, verbose_name="Anomalie détectée")),
                ("anomaly_score", models.FloatField(
                    help_text="Plus le score est élevé, plus l'événement est anormal (0.0 à 1.0).",
                    verbose_name="Score d'anomalie",
                )),
                ("predicted_at", models.DateTimeField(auto_now_add=True, verbose_name="Prédit le")),
                ("log", models.OneToOneField(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name="prediction",
                    to="logs.normalizedlog",
                    verbose_name="Log analysé",
                )),
                ("model", models.ForeignKey(
                    blank=True,
                    null=True,
                    on_delete=django.db.models.deletion.SET_NULL,
                    related_name="predictions",
                    to="ml.mlmodel",
                    verbose_name="Modèle utilisé",
                )),
            ],
            options={
                "verbose_name": "Prédiction ML",
                "verbose_name_plural": "Prédictions ML",
                "ordering": ["-predicted_at"],
            },
        ),
        migrations.AddIndex(
            model_name="prediction",
            index=models.Index(fields=["is_anomaly", "predicted_at"], name="ml_pred_anomaly_time_idx"),
        ),
        migrations.AddIndex(
            model_name="prediction",
            index=models.Index(fields=["anomaly_score"], name="ml_pred_score_idx"),
        ),
    ]
