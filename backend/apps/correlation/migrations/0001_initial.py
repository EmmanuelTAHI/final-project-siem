import uuid
import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    initial = True

    dependencies = [
        ("logs", "0001_initial"),
        ("alerts", "0001_initial"),
        ("users", "0001_initial"),
    ]

    operations = [
        migrations.CreateModel(
            name="CorrelationRule",
            fields=[
                ("id", models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ("name", models.CharField(max_length=255, unique=True, verbose_name="Nom de la règle")),
                ("description", models.TextField(verbose_name="Description")),
                ("is_active", models.BooleanField(default=True, verbose_name="Active")),
                ("severity", models.CharField(
                    choices=[
                        ("low", "Faible"),
                        ("medium", "Moyen"),
                        ("high", "Élevé"),
                        ("critical", "Critique"),
                    ],
                    max_length=20,
                    verbose_name="Sévérité",
                )),
                ("condition_logic", models.JSONField(
                    help_text="Ex: {'type': 'threshold', 'field': 'user_email', 'action': 'login_failure', 'count': 5, 'window_seconds': 300}",
                    verbose_name="Logique de condition",
                )),
                ("alert_title_template", models.CharField(
                    help_text="Ex: Brute force détecté sur {user_email}",
                    max_length=500,
                    verbose_name="Template de titre d'alerte",
                )),
                ("mitre_tactic", models.CharField(blank=True, max_length=100, null=True, verbose_name="MITRE Tactic")),
                ("mitre_technique", models.CharField(blank=True, max_length=200, null=True, verbose_name="MITRE Technique")),
                ("created_at", models.DateTimeField(auto_now_add=True, verbose_name="Créé le")),
                ("updated_at", models.DateTimeField(auto_now=True, verbose_name="Modifié le")),
                ("created_by", models.ForeignKey(
                    blank=True,
                    null=True,
                    on_delete=django.db.models.deletion.SET_NULL,
                    related_name="correlation_rules",
                    to=settings.AUTH_USER_MODEL,
                    verbose_name="Créé par",
                )),
            ],
            options={
                "verbose_name": "Règle de corrélation",
                "verbose_name_plural": "Règles de corrélation",
                "ordering": ["name"],
            },
        ),
        migrations.CreateModel(
            name="RuleMatch",
            fields=[
                ("id", models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ("matched_at", models.DateTimeField(auto_now_add=True, verbose_name="Correspondance le")),
                ("alert", models.ForeignKey(
                    blank=True,
                    null=True,
                    on_delete=django.db.models.deletion.SET_NULL,
                    related_name="rule_matches",
                    to="alerts.alert",
                    verbose_name="Alerte générée",
                )),
                ("logs", models.ManyToManyField(
                    blank=True,
                    related_name="rule_matches",
                    to="logs.normalizedlog",
                    verbose_name="Logs déclencheurs",
                )),
                ("rule", models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name="matches",
                    to="correlation.correlationrule",
                    verbose_name="Règle",
                )),
            ],
            options={
                "verbose_name": "Correspondance de règle",
                "verbose_name_plural": "Correspondances de règles",
                "ordering": ["-matched_at"],
            },
        ),
    ]
