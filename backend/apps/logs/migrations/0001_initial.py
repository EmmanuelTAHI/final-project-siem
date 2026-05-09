import uuid
import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    initial = True

    dependencies = [
        ("collectors", "0001_initial"),
    ]

    operations = [
        migrations.CreateModel(
            name="RawLog",
            fields=[
                ("id", models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ("source_type", models.CharField(
                    choices=[
                        ("microsoft365", "Microsoft 365"),
                        ("google_workspace", "Google Workspace"),
                        ("wazuh", "Wazuh"),
                        ("syslog", "Syslog"),
                        ("manual", "Manuel"),
                    ],
                    max_length=50,
                    verbose_name="Type de source",
                )),
                ("raw_data", models.JSONField(verbose_name="Données brutes")),
                ("received_at", models.DateTimeField(auto_now_add=True, verbose_name="Reçu le")),
                ("is_normalized", models.BooleanField(default=False, verbose_name="Normalisé")),
                ("connector", models.ForeignKey(
                    blank=True,
                    null=True,
                    on_delete=django.db.models.deletion.SET_NULL,
                    related_name="raw_logs",
                    to="collectors.connectorconfig",
                    verbose_name="Connecteur",
                )),
            ],
            options={
                "verbose_name": "Log brut",
                "verbose_name_plural": "Logs bruts",
                "ordering": ["-received_at"],
            },
        ),
        migrations.CreateModel(
            name="NormalizedLog",
            fields=[
                ("id", models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ("event_time", models.DateTimeField(db_index=True, verbose_name="Horodatage de l'événement")),
                ("source_ip", models.GenericIPAddressField(blank=True, null=True, verbose_name="IP source")),
                ("destination_ip", models.GenericIPAddressField(blank=True, null=True, verbose_name="IP destination")),
                ("user_email", models.CharField(blank=True, db_index=True, max_length=320, null=True, verbose_name="Email utilisateur")),
                ("user_id", models.CharField(blank=True, max_length=255, null=True, verbose_name="ID utilisateur source")),
                ("action", models.CharField(
                    db_index=True,
                    help_text="Ex: login_success, login_failure, file_download, privilege_change",
                    max_length=100,
                    verbose_name="Action",
                )),
                ("outcome", models.CharField(
                    choices=[("success", "Succès"), ("failure", "Échec"), ("unknown", "Inconnu")],
                    default="unknown",
                    max_length=20,
                    verbose_name="Résultat",
                )),
                ("resource", models.CharField(blank=True, max_length=500, null=True, verbose_name="Ressource accédée")),
                ("geo_country", models.CharField(blank=True, max_length=2, null=True, verbose_name="Pays (ISO 3166-1 alpha-2)")),
                ("geo_city", models.CharField(blank=True, max_length=100, null=True, verbose_name="Ville")),
                ("geo_latitude", models.FloatField(blank=True, null=True, verbose_name="Latitude")),
                ("geo_longitude", models.FloatField(blank=True, null=True, verbose_name="Longitude")),
                ("user_agent", models.TextField(blank=True, null=True, verbose_name="User-Agent")),
                ("severity", models.CharField(
                    choices=[
                        ("info", "Info"),
                        ("low", "Faible"),
                        ("medium", "Moyen"),
                        ("high", "Élevé"),
                        ("critical", "Critique"),
                    ],
                    db_index=True,
                    default="info",
                    max_length=20,
                    verbose_name="Sévérité",
                )),
                ("source_type", models.CharField(db_index=True, max_length=50, verbose_name="Type de source")),
                ("extra_fields", models.JSONField(blank=True, default=dict, verbose_name="Champs supplémentaires")),
                ("indexed_at", models.DateTimeField(auto_now_add=True, db_index=True, verbose_name="Indexé le")),
                ("raw_log", models.OneToOneField(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name="normalized",
                    to="logs.rawlog",
                    verbose_name="Log brut",
                )),
            ],
            options={
                "verbose_name": "Log normalisé",
                "verbose_name_plural": "Logs normalisés",
                "ordering": ["-event_time"],
            },
        ),
        migrations.AddIndex(
            model_name="rawlog",
            index=models.Index(fields=["source_type", "received_at"], name="logs_raw_source_received_idx"),
        ),
        migrations.AddIndex(
            model_name="rawlog",
            index=models.Index(fields=["is_normalized"], name="logs_raw_normalized_idx"),
        ),
        migrations.AddIndex(
            model_name="rawlog",
            index=models.Index(fields=["connector"], name="logs_raw_connector_idx"),
        ),
        migrations.AddIndex(
            model_name="normalizedlog",
            index=models.Index(fields=["source_type", "event_time"], name="logs_norm_source_time_idx"),
        ),
        migrations.AddIndex(
            model_name="normalizedlog",
            index=models.Index(fields=["user_email", "event_time"], name="logs_norm_user_time_idx"),
        ),
        migrations.AddIndex(
            model_name="normalizedlog",
            index=models.Index(fields=["action", "outcome"], name="logs_norm_action_outcome_idx"),
        ),
        migrations.AddIndex(
            model_name="normalizedlog",
            index=models.Index(fields=["geo_country"], name="logs_norm_country_idx"),
        ),
        migrations.AddIndex(
            model_name="normalizedlog",
            index=models.Index(fields=["severity", "event_time"], name="logs_norm_severity_time_idx"),
        ),
    ]
