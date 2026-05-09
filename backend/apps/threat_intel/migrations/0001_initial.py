import uuid
import django.db.models.deletion
import django.utils.timezone
from django.db import migrations, models


class Migration(migrations.Migration):

    initial = True

    dependencies = [
        ("logs", "0001_initial"),
    ]

    operations = [
        migrations.CreateModel(
            name="ThreatIndicator",
            fields=[
                ("id", models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ("indicator_type", models.CharField(
                    choices=[
                        ("ip", "Adresse IP"),
                        ("domain", "Domaine"),
                        ("hash_md5", "Hash MD5"),
                        ("hash_sha256", "Hash SHA256"),
                        ("url", "URL"),
                        ("email", "Email"),
                    ],
                    db_index=True,
                    max_length=20,
                )),
                ("value", models.CharField(db_index=True, max_length=512)),
                ("reputation_score", models.FloatField(default=0.0)),
                ("confidence", models.FloatField(default=0.0)),
                ("source", models.CharField(
                    choices=[
                        ("abuseipdb", "AbuseIPDB"),
                        ("virustotal", "VirusTotal"),
                        ("manual", "Manuel"),
                        ("otx", "AlienVault OTX"),
                    ],
                    default="abuseipdb",
                    max_length=30,
                )),
                ("tags", models.JSONField(blank=True, default=list)),
                ("raw_data", models.JSONField(blank=True, default=dict)),
                ("is_malicious", models.BooleanField(db_index=True, default=False)),
                ("last_seen", models.DateTimeField(default=django.utils.timezone.now)),
                ("first_seen", models.DateTimeField(default=django.utils.timezone.now)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
            ],
            options={
                "ordering": ["-reputation_score"],
                "unique_together": {("indicator_type", "value", "source")},
            },
        ),
        migrations.AddIndex(
            model_name="threatindicator",
            index=models.Index(fields=["indicator_type", "is_malicious"], name="threat_ind_type_malicious_idx"),
        ),
        migrations.AddIndex(
            model_name="threatindicator",
            index=models.Index(fields=["reputation_score"], name="threat_ind_score_idx"),
        ),
        migrations.CreateModel(
            name="EnrichedLog",
            fields=[
                ("id", models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ("max_score", models.FloatField(default=0.0)),
                ("is_threat", models.BooleanField(db_index=True, default=False)),
                ("enriched_at", models.DateTimeField(auto_now_add=True)),
                ("indicators", models.ManyToManyField(blank=True, to="threat_intel.threatindicator")),
                ("log", models.OneToOneField(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name="cti_enrichment",
                    to="logs.normalizedlog",
                )),
            ],
            options={"ordering": ["-enriched_at"]},
        ),
    ]
