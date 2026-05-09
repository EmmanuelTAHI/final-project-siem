import uuid
import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    initial = True

    dependencies = [
        ("logs", "0001_initial"),
        ("users", "0001_initial"),
    ]

    operations = [
        migrations.CreateModel(
            name="Alert",
            fields=[
                ("id", models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ("title", models.CharField(max_length=500, verbose_name="Titre")),
                ("description", models.TextField(verbose_name="Description")),
                ("severity", models.CharField(
                    choices=[
                        ("low", "Faible"),
                        ("medium", "Moyen"),
                        ("high", "Élevé"),
                        ("critical", "Critique"),
                    ],
                    db_index=True,
                    max_length=20,
                    verbose_name="Sévérité",
                )),
                ("status", models.CharField(
                    choices=[
                        ("open", "Ouverte"),
                        ("in_progress", "En cours"),
                        ("resolved", "Résolue"),
                        ("false_positive", "Faux positif"),
                    ],
                    db_index=True,
                    default="open",
                    max_length=20,
                    verbose_name="Statut",
                )),
                ("created_at", models.DateTimeField(auto_now_add=True, db_index=True, verbose_name="Créée le")),
                ("updated_at", models.DateTimeField(auto_now=True, verbose_name="Modifiée le")),
                ("resolved_at", models.DateTimeField(blank=True, null=True, verbose_name="Résolue le")),
                ("resolution_note", models.TextField(blank=True, null=True, verbose_name="Note de résolution")),
                ("assigned_to", models.ForeignKey(
                    blank=True,
                    null=True,
                    on_delete=django.db.models.deletion.SET_NULL,
                    related_name="assigned_alerts",
                    to=settings.AUTH_USER_MODEL,
                    verbose_name="Assignée à",
                )),
                ("source_logs", models.ManyToManyField(
                    blank=True,
                    related_name="alerts",
                    to="logs.normalizedlog",
                    verbose_name="Logs sources",
                )),
            ],
            options={
                "verbose_name": "Alerte",
                "verbose_name_plural": "Alertes",
                "ordering": ["-created_at"],
            },
        ),
        migrations.CreateModel(
            name="AlertComment",
            fields=[
                ("id", models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ("content", models.TextField(verbose_name="Contenu")),
                ("created_at", models.DateTimeField(auto_now_add=True, verbose_name="Créé le")),
                ("alert", models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name="comments",
                    to="alerts.alert",
                    verbose_name="Alerte",
                )),
                ("author", models.ForeignKey(
                    blank=True,
                    null=True,
                    on_delete=django.db.models.deletion.SET_NULL,
                    related_name="alert_comments",
                    to=settings.AUTH_USER_MODEL,
                    verbose_name="Auteur",
                )),
            ],
            options={
                "verbose_name": "Commentaire d'alerte",
                "verbose_name_plural": "Commentaires d'alertes",
                "ordering": ["created_at"],
            },
        ),
        migrations.AddIndex(
            model_name="alert",
            index=models.Index(fields=["severity", "status"], name="alerts_severity_status_idx"),
        ),
        migrations.AddIndex(
            model_name="alert",
            index=models.Index(fields=["status", "created_at"], name="alerts_status_created_idx"),
        ),
        migrations.AddIndex(
            model_name="alert",
            index=models.Index(fields=["assigned_to", "status"], name="alerts_assigned_status_idx"),
        ),
    ]
