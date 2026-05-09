import uuid
import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    initial = True

    dependencies = [
        ("users", "0001_initial"),
    ]

    operations = [
        migrations.CreateModel(
            name="ConnectorConfig",
            fields=[
                ("id", models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ("name", models.CharField(max_length=255, verbose_name="Nom du connecteur")),
                ("source_type", models.CharField(
                    choices=[
                        ("microsoft365", "Microsoft 365"),
                        ("google_workspace", "Google Workspace"),
                        ("wazuh", "Wazuh SIEM"),
                        ("syslog", "Syslog"),
                    ],
                    max_length=50,
                    verbose_name="Type de source",
                )),
                ("credentials_encrypted", models.TextField(blank=True, default="", verbose_name="Credentials chiffrés (Fernet)")),
                ("oauth_access_token", models.TextField(blank=True, null=True, verbose_name="Access Token OAuth2 (chiffré)")),
                ("oauth_refresh_token", models.TextField(blank=True, null=True, verbose_name="Refresh Token OAuth2 (chiffré)")),
                ("token_expires_at", models.DateTimeField(blank=True, null=True, verbose_name="Expiration du token")),
                ("is_active", models.BooleanField(default=True, verbose_name="Actif")),
                ("polling_interval_seconds", models.IntegerField(default=300, verbose_name="Intervalle de collecte (secondes)")),
                ("last_collected_at", models.DateTimeField(blank=True, null=True, verbose_name="Dernière collecte")),
                ("created_at", models.DateTimeField(auto_now_add=True, verbose_name="Créé le")),
                ("created_by", models.ForeignKey(
                    blank=True,
                    null=True,
                    on_delete=django.db.models.deletion.SET_NULL,
                    related_name="connectors",
                    to=settings.AUTH_USER_MODEL,
                    verbose_name="Créé par",
                )),
            ],
            options={
                "verbose_name": "Connecteur",
                "verbose_name_plural": "Connecteurs",
                "ordering": ["-created_at"],
            },
        ),
        migrations.CreateModel(
            name="CollectionJob",
            fields=[
                ("id", models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ("status", models.CharField(
                    choices=[
                        ("pending", "En attente"),
                        ("running", "En cours"),
                        ("success", "Succès"),
                        ("failed", "Échoué"),
                    ],
                    default="pending",
                    max_length=20,
                    verbose_name="Statut",
                )),
                ("logs_collected_count", models.IntegerField(default=0, verbose_name="Logs collectés")),
                ("error_message", models.TextField(blank=True, null=True, verbose_name="Message d'erreur")),
                ("started_at", models.DateTimeField(blank=True, null=True, verbose_name="Démarré le")),
                ("finished_at", models.DateTimeField(blank=True, null=True, verbose_name="Terminé le")),
                ("connector", models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name="jobs",
                    to="collectors.connectorconfig",
                    verbose_name="Connecteur",
                )),
            ],
            options={
                "verbose_name": "Job de collecte",
                "verbose_name_plural": "Jobs de collecte",
                "ordering": ["-started_at"],
            },
        ),
        migrations.AddIndex(
            model_name="collectionjob",
            index=models.Index(fields=["connector", "status"], name="collectors_job_connector_status_idx"),
        ),
        migrations.AddIndex(
            model_name="collectionjob",
            index=models.Index(fields=["started_at"], name="collectors_job_started_at_idx"),
        ),
    ]
