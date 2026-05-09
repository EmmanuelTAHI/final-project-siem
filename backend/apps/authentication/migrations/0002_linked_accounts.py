"""Migration : LinkedAccount, ProviderLoginEvent, LoginConfirmation, SecurityNotification."""
import uuid

import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("authentication", "0001_initial"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name="LinkedAccount",
            fields=[
                ("id", models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ("provider", models.CharField(choices=[("google", "Google"), ("microsoft", "Microsoft"), ("github", "GitHub")], max_length=20)),
                ("provider_user_id", models.CharField(db_index=True, max_length=255)),
                ("provider_email", models.EmailField(max_length=254)),
                ("provider_display_name", models.CharField(blank=True, default="", max_length=255)),
                ("avatar_url", models.URLField(blank=True, default="")),
                ("access_token_encrypted", models.TextField(blank=True, default="")),
                ("refresh_token_encrypted", models.TextField(blank=True, default="")),
                ("token_expires_at", models.DateTimeField(blank=True, null=True)),
                ("scopes", models.TextField(blank=True, default="")),
                ("status", models.CharField(choices=[("active", "Actif"), ("paused", "En pause"), ("revoked", "Révoqué"), ("error", "Erreur")], default="active", max_length=20)),
                ("last_event_id", models.CharField(blank=True, default="", max_length=255)),
                ("last_polled_at", models.DateTimeField(blank=True, null=True)),
                ("linked_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("user", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="linked_accounts", to=settings.AUTH_USER_MODEL, verbose_name="Propriétaire Log+")),
            ],
            options={
                "verbose_name": "Compte lié",
                "verbose_name_plural": "Comptes liés",
                "ordering": ["-linked_at"],
            },
        ),
        migrations.AddConstraint(
            model_name="linkedaccount",
            constraint=models.UniqueConstraint(
                fields=("user", "provider", "provider_user_id"),
                name="unique_linked_account_per_user",
            ),
        ),
        migrations.AddIndex(
            model_name="linkedaccount",
            index=models.Index(fields=["user", "provider"], name="auth_linked_user_provid_idx"),
        ),
        migrations.AddIndex(
            model_name="linkedaccount",
            index=models.Index(fields=["status", "last_polled_at"], name="auth_linked_status_polled_idx"),
        ),
        migrations.CreateModel(
            name="ProviderLoginEvent",
            fields=[
                ("id", models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ("event_type", models.CharField(choices=[("login_success", "Connexion réussie"), ("login_failure", "Échec de connexion"), ("mfa_challenge", "Défi MFA"), ("mfa_failure", "Échec MFA"), ("password_reset", "Réinitialisation MDP"), ("suspicious_activity", "Activité suspecte"), ("token_revoked", "Token révoqué"), ("unknown", "Inconnu")], default="unknown", max_length=30)),
                ("provider_event_id", models.CharField(db_index=True, max_length=255)),
                ("occurred_at", models.DateTimeField(db_index=True)),
                ("ip_address", models.GenericIPAddressField(blank=True, null=True)),
                ("user_agent", models.TextField(blank=True, default="")),
                ("browser", models.CharField(blank=True, default="", max_length=50)),
                ("os", models.CharField(blank=True, default="", max_length=50)),
                ("device_type", models.CharField(blank=True, default="", max_length=30)),
                ("geo_country", models.CharField(blank=True, default="", max_length=2)),
                ("geo_city", models.CharField(blank=True, default="", max_length=120)),
                ("geo_latitude", models.FloatField(blank=True, null=True)),
                ("geo_longitude", models.FloatField(blank=True, null=True)),
                ("is_known_device", models.BooleanField(default=False)),
                ("is_known_location", models.BooleanField(default=False)),
                ("risk_score", models.PositiveSmallIntegerField(default=0)),
                ("raw", models.JSONField(blank=True, default=dict)),
                ("received_at", models.DateTimeField(auto_now_add=True)),
                ("linked_account", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="login_events", to="authentication.linkedaccount")),
            ],
            options={
                "verbose_name": "Événement provider",
                "verbose_name_plural": "Événements providers",
                "ordering": ["-occurred_at"],
            },
        ),
        migrations.AddConstraint(
            model_name="providerloginevent",
            constraint=models.UniqueConstraint(
                fields=("linked_account", "provider_event_id"),
                name="unique_provider_event",
            ),
        ),
        migrations.AddIndex(
            model_name="providerloginevent",
            index=models.Index(fields=["linked_account", "occurred_at"], name="auth_evt_acc_time_idx"),
        ),
        migrations.AddIndex(
            model_name="providerloginevent",
            index=models.Index(fields=["event_type", "occurred_at"], name="auth_evt_type_time_idx"),
        ),
        migrations.CreateModel(
            name="LoginConfirmation",
            fields=[
                ("id", models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ("status", models.CharField(choices=[("pending", "En attente"), ("approved", "Confirmée par l'utilisateur"), ("rejected", "Rejetée par l'utilisateur"), ("expired", "Expirée")], default="pending", max_length=20)),
                ("ip_address", models.GenericIPAddressField(blank=True, null=True)),
                ("browser", models.CharField(blank=True, default="", max_length=50)),
                ("os", models.CharField(blank=True, default="", max_length=50)),
                ("device_type", models.CharField(blank=True, default="", max_length=30)),
                ("geo_city", models.CharField(blank=True, default="", max_length=120)),
                ("geo_country", models.CharField(blank=True, default="", max_length=2)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("expires_at", models.DateTimeField()),
                ("responded_at", models.DateTimeField(blank=True, null=True)),
                ("responded_ip", models.GenericIPAddressField(blank=True, null=True)),
                ("event", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="confirmations", to="authentication.providerloginevent")),
                ("linked_account", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.CASCADE, related_name="confirmations", to="authentication.linkedaccount")),
                ("user", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="login_confirmations", to=settings.AUTH_USER_MODEL)),
            ],
            options={
                "verbose_name": "Confirmation de connexion",
                "verbose_name_plural": "Confirmations de connexion",
                "ordering": ["-created_at"],
            },
        ),
        migrations.AddIndex(
            model_name="loginconfirmation",
            index=models.Index(fields=["user", "status"], name="auth_conf_user_status_idx"),
        ),
        migrations.AddIndex(
            model_name="loginconfirmation",
            index=models.Index(fields=["status", "expires_at"], name="auth_conf_status_exp_idx"),
        ),
        migrations.CreateModel(
            name="SecurityNotification",
            fields=[
                ("id", models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ("kind", models.CharField(choices=[("login_new_device", "Nouvelle connexion (device inconnu)"), ("login_new_location", "Nouvelle connexion (lieu inconnu)"), ("brute_force", "Tentative de brute-force"), ("account_locked", "Compte verrouillé"), ("account_unlinked", "Compte délié"), ("provider_error", "Erreur provider"), ("info", "Information")], max_length=40)),
                ("level", models.CharField(choices=[("info", "Information"), ("warning", "Avertissement"), ("critical", "Critique")], default="info", max_length=20)),
                ("title", models.CharField(max_length=200)),
                ("body", models.TextField(blank=True, default="")),
                ("metadata", models.JSONField(blank=True, default=dict)),
                ("is_read", models.BooleanField(default=False)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("read_at", models.DateTimeField(blank=True, null=True)),
                ("confirmation", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="notifications", to="authentication.loginconfirmation")),
                ("linked_account", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="notifications", to="authentication.linkedaccount")),
                ("user", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="security_notifications", to=settings.AUTH_USER_MODEL)),
            ],
            options={
                "verbose_name": "Notification sécurité",
                "verbose_name_plural": "Notifications sécurité",
                "ordering": ["-created_at"],
            },
        ),
        migrations.AddIndex(
            model_name="securitynotification",
            index=models.Index(fields=["user", "is_read", "created_at"], name="auth_notif_user_read_idx"),
        ),
        migrations.AddIndex(
            model_name="securitynotification",
            index=models.Index(fields=["kind", "created_at"], name="auth_notif_kind_time_idx"),
        ),
    ]
