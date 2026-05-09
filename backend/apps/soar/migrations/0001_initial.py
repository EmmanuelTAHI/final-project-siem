import uuid
import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    initial = True

    dependencies = [
        ("alerts", "0001_initial"),
        ("users", "0001_initial"),
    ]

    operations = [
        migrations.CreateModel(
            name="Playbook",
            fields=[
                ("id", models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ("name", models.CharField(max_length=200, unique=True)),
                ("description", models.TextField(blank=True)),
                ("trigger_type", models.CharField(
                    choices=[
                        ("severity", "Seuil de sévérité"),
                        ("rule_match", "Règle de corrélation"),
                        ("ml_anomaly", "Anomalie ML"),
                        ("cti_match", "Correspondance CTI"),
                        ("manual", "Manuel"),
                    ],
                    default="severity",
                    max_length=30,
                )),
                ("trigger_conditions", models.JSONField(default=dict)),
                ("actions", models.JSONField(default=list)),
                ("is_active", models.BooleanField(db_index=True, default=True)),
                ("execution_count", models.PositiveIntegerField(default=0)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("created_by", models.ForeignKey(
                    null=True,
                    on_delete=django.db.models.deletion.SET_NULL,
                    related_name="playbooks",
                    to=settings.AUTH_USER_MODEL,
                )),
            ],
            options={"ordering": ["name"]},
        ),
        migrations.CreateModel(
            name="PlaybookExecution",
            fields=[
                ("id", models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ("status", models.CharField(
                    choices=[
                        ("pending", "En attente"),
                        ("running", "En cours"),
                        ("success", "Succès"),
                        ("partial", "Partiel"),
                        ("failed", "Échoué"),
                    ],
                    db_index=True,
                    default="pending",
                    max_length=20,
                )),
                ("actions_taken", models.JSONField(default=list)),
                ("error_message", models.TextField(blank=True)),
                ("triggered_by", models.CharField(default="automatic", max_length=50)),
                ("started_at", models.DateTimeField(auto_now_add=True)),
                ("finished_at", models.DateTimeField(blank=True, null=True)),
                ("alert", models.ForeignKey(
                    blank=True,
                    null=True,
                    on_delete=django.db.models.deletion.SET_NULL,
                    related_name="playbook_executions",
                    to="alerts.alert",
                )),
                ("playbook", models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name="executions",
                    to="soar.playbook",
                )),
            ],
            options={"ordering": ["-started_at"]},
        ),
    ]
