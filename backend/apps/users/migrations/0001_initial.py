import uuid
import django.contrib.auth.validators
import django.db.models.deletion
import django.utils.timezone
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    initial = True

    dependencies = [
        ("auth", "0012_alter_user_first_name_max_length"),
    ]

    operations = [
        migrations.CreateModel(
            name="User",
            fields=[
                ("password", models.CharField(max_length=128, verbose_name="password")),
                ("last_login", models.DateTimeField(blank=True, null=True, verbose_name="last login")),
                ("is_superuser", models.BooleanField(default=False, verbose_name="superuser status")),
                ("username", models.CharField(
                    error_messages={"unique": "A user with that username already exists."},
                    max_length=150,
                    unique=True,
                    validators=[django.contrib.auth.validators.UnicodeUsernameValidator()],
                    verbose_name="username",
                )),
                ("date_joined", models.DateTimeField(default=django.utils.timezone.now, verbose_name="date joined")),
                ("id", models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ("email", models.EmailField(max_length=254, unique=True, verbose_name="Adresse email")),
                ("first_name", models.CharField(max_length=150, verbose_name="Prénom")),
                ("last_name", models.CharField(max_length=150, verbose_name="Nom")),
                ("role", models.CharField(
                    choices=[("admin", "Administrateur"), ("analyst", "Analyste SOC"), ("viewer", "Observateur")],
                    default="viewer",
                    max_length=20,
                    verbose_name="Rôle",
                )),
                ("is_active", models.BooleanField(default=True, verbose_name="Actif")),
                ("is_staff", models.BooleanField(default=False, verbose_name="staff status")),
                ("created_at", models.DateTimeField(auto_now_add=True, verbose_name="Créé le")),
                ("updated_at", models.DateTimeField(auto_now=True, verbose_name="Modifié le")),
                ("groups", models.ManyToManyField(
                    blank=True,
                    help_text="The groups this user belongs to.",
                    related_name="user_set",
                    related_query_name="user",
                    to="auth.group",
                    verbose_name="groups",
                )),
                ("user_permissions", models.ManyToManyField(
                    blank=True,
                    help_text="Specific permissions for this user.",
                    related_name="user_set",
                    related_query_name="user",
                    to="auth.permission",
                    verbose_name="user permissions",
                )),
            ],
            options={
                "verbose_name": "Utilisateur",
                "verbose_name_plural": "Utilisateurs",
                "ordering": ["-created_at"],
            },
        ),
        migrations.CreateModel(
            name="AuditTrail",
            fields=[
                ("id", models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ("action", models.CharField(help_text="Ex: login, logout, rule_create, alert_update", max_length=100, verbose_name="Action")),
                ("target_model", models.CharField(blank=True, default="", help_text="Ex: Alert, CorrelationRule, ConnectorConfig", max_length=100, verbose_name="Modèle cible")),
                ("target_id", models.CharField(blank=True, max_length=255, null=True, verbose_name="ID de la cible")),
                ("ip_address", models.GenericIPAddressField(blank=True, null=True, verbose_name="Adresse IP")),
                ("user_agent", models.TextField(blank=True, null=True, verbose_name="User-Agent")),
                ("extra_data", models.JSONField(blank=True, default=dict, verbose_name="Données supplémentaires")),
                ("timestamp", models.DateTimeField(auto_now_add=True, verbose_name="Horodatage")),
                ("user", models.ForeignKey(
                    blank=True,
                    null=True,
                    on_delete=django.db.models.deletion.SET_NULL,
                    related_name="audit_trails",
                    to=settings.AUTH_USER_MODEL,
                    verbose_name="Utilisateur",
                )),
            ],
            options={
                "verbose_name": "Audit Trail",
                "verbose_name_plural": "Audit Trails",
                "ordering": ["-timestamp"],
            },
        ),
        migrations.AddIndex(
            model_name="audittrail",
            index=models.Index(fields=["user", "timestamp"], name="users_audit_user_id_idx"),
        ),
        migrations.AddIndex(
            model_name="audittrail",
            index=models.Index(fields=["action", "timestamp"], name="users_audit_action_idx"),
        ),
        migrations.AddIndex(
            model_name="audittrail",
            index=models.Index(fields=["target_model", "target_id"], name="users_audit_target_idx"),
        ),
    ]
