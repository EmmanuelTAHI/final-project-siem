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
            name="HuntingQuery",
            fields=[
                ("id", models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ("name", models.CharField(max_length=200)),
                ("description", models.TextField(blank=True)),
                ("query_params", models.JSONField(default=dict)),
                ("mitre_tactic", models.CharField(blank=True, max_length=100)),
                ("mitre_technique", models.CharField(blank=True, max_length=100)),
                ("last_run_at", models.DateTimeField(blank=True, null=True)),
                ("last_results_count", models.PositiveIntegerField(default=0)),
                ("run_count", models.PositiveIntegerField(default=0)),
                ("is_scheduled", models.BooleanField(default=False)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("created_by", models.ForeignKey(
                    null=True,
                    on_delete=django.db.models.deletion.SET_NULL,
                    related_name="hunting_queries",
                    to=settings.AUTH_USER_MODEL,
                )),
            ],
            options={"ordering": ["-updated_at"]},
        ),
        migrations.CreateModel(
            name="HuntingResult",
            fields=[
                ("id", models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ("executed_at", models.DateTimeField(auto_now_add=True)),
                ("log", models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE,
                    to="logs.normalizedlog",
                )),
                ("query", models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name="results",
                    to="hunting.huntingquery",
                )),
            ],
            options={
                "ordering": ["-executed_at"],
                "unique_together": {("query", "log")},
            },
        ),
    ]
