"""
Modèles de l'app authentication.

Trois entités persistées (les states OAuth restent dans Redis) :

- LinkedAccount       : compte tiers (Google / Microsoft / GitHub) lié à un utilisateur de Log+.
- ProviderLoginEvent  : événement de sécurité (login, échec, MFA, etc.) capté chez le provider.
- LoginConfirmation   : ticket signé envoyé à l'utilisateur pour confirmer/rejeter une connexion.
- SecurityNotification: notification persistante (cloche dans la topbar).
"""
import uuid

from django.conf import settings
from django.db import models


# ─────────────────────────────────────────────────────────────────────────────
# LinkedAccount
# ─────────────────────────────────────────────────────────────────────────────


class LinkedAccount(models.Model):
    """
    Compte OAuth d'un service tiers lié à un utilisateur de Log+.

    Log+ monitore l'activité de connexion sur ce compte (brute force,
    nouvelle géoloc, nouveau device) et peut révoquer la session côté
    provider en cas d'incident confirmé.
    """

    PROVIDER_CHOICES = [
        ("google", "Google"),
        ("microsoft", "Microsoft"),
        ("github", "GitHub"),
    ]

    STATUS_CHOICES = [
        ("active", "Actif"),
        ("paused", "En pause"),
        ("revoked", "Révoqué"),
        ("error", "Erreur"),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="linked_accounts",
        verbose_name="Propriétaire Log+",
    )
    provider = models.CharField(max_length=20, choices=PROVIDER_CHOICES)
    provider_user_id = models.CharField(max_length=255, db_index=True)
    provider_email = models.EmailField()
    provider_display_name = models.CharField(max_length=255, blank=True, default="")
    avatar_url = models.URLField(blank=True, default="")

    # Tokens chiffrés (utils/encryption.py — Fernet)
    access_token_encrypted = models.TextField(blank=True, default="")
    refresh_token_encrypted = models.TextField(blank=True, default="")
    token_expires_at = models.DateTimeField(null=True, blank=True)
    scopes = models.TextField(blank=True, default="")

    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default="active")
    last_event_id = models.CharField(max_length=255, blank=True, default="")
    last_polled_at = models.DateTimeField(null=True, blank=True)
    linked_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Compte lié"
        verbose_name_plural = "Comptes liés"
        ordering = ["-linked_at"]
        constraints = [
            models.UniqueConstraint(
                fields=["user", "provider", "provider_user_id"],
                name="unique_linked_account_per_user",
            ),
        ]
        indexes = [
            models.Index(fields=["user", "provider"]),
            models.Index(fields=["status", "last_polled_at"]),
        ]

    def __str__(self):
        return f"{self.user.email} ↔ {self.provider}:{self.provider_email}"


# ─────────────────────────────────────────────────────────────────────────────
# ProviderLoginEvent
# ─────────────────────────────────────────────────────────────────────────────


class ProviderLoginEvent(models.Model):
    """
    Événement de sécurité capté chez un provider pour un LinkedAccount donné.

    Les ProviderLoginEvent sont aussi normalisés vers `apps.logs.NormalizedLog`
    pour bénéficier du moteur de corrélation, mais on garde une copie locale
    pour faciliter l'affichage par utilisateur (UI Comptes liés).
    """

    EVENT_TYPES = [
        ("login_success", "Connexion réussie"),
        ("login_failure", "Échec de connexion"),
        ("mfa_challenge", "Défi MFA"),
        ("mfa_failure", "Échec MFA"),
        ("password_reset", "Réinitialisation MDP"),
        ("suspicious_activity", "Activité suspecte"),
        ("token_revoked", "Token révoqué"),
        ("unknown", "Inconnu"),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    linked_account = models.ForeignKey(
        LinkedAccount,
        on_delete=models.CASCADE,
        related_name="login_events",
    )
    event_type = models.CharField(max_length=30, choices=EVENT_TYPES, default="unknown")
    provider_event_id = models.CharField(max_length=255, db_index=True)
    occurred_at = models.DateTimeField(db_index=True)

    ip_address = models.GenericIPAddressField(null=True, blank=True)
    user_agent = models.TextField(blank=True, default="")
    browser = models.CharField(max_length=50, blank=True, default="")
    os = models.CharField(max_length=50, blank=True, default="")
    device_type = models.CharField(max_length=30, blank=True, default="")  # desktop/mobile/server

    geo_country = models.CharField(max_length=2, blank=True, default="")
    geo_city = models.CharField(max_length=120, blank=True, default="")
    geo_latitude = models.FloatField(null=True, blank=True)
    geo_longitude = models.FloatField(null=True, blank=True)

    is_known_device = models.BooleanField(default=False)
    is_known_location = models.BooleanField(default=False)
    risk_score = models.PositiveSmallIntegerField(default=0)  # 0..100

    raw = models.JSONField(default=dict, blank=True)
    received_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "Événement provider"
        verbose_name_plural = "Événements providers"
        ordering = ["-occurred_at"]
        constraints = [
            models.UniqueConstraint(
                fields=["linked_account", "provider_event_id"],
                name="unique_provider_event",
            ),
        ]
        indexes = [
            models.Index(fields=["linked_account", "occurred_at"]),
            models.Index(fields=["event_type", "occurred_at"]),
        ]

    def __str__(self):
        return f"{self.linked_account.provider}:{self.event_type} @ {self.occurred_at:%Y-%m-%d %H:%M}"


# ─────────────────────────────────────────────────────────────────────────────
# LoginConfirmation
# ─────────────────────────────────────────────────────────────────────────────


class LoginConfirmation(models.Model):
    """
    Ticket "Est-ce bien vous ?" envoyé à l'utilisateur sur un nouveau device.

    Le token signé envoyé par mail contient l'id de cette ligne.
    L'utilisateur clique "C'est moi" → status=approved, "Pas moi" → rejected
    (déclenche la révocation côté provider).
    """

    STATUS_CHOICES = [
        ("pending", "En attente"),
        ("approved", "Confirmée par l'utilisateur"),
        ("rejected", "Rejetée par l'utilisateur"),
        ("expired", "Expirée"),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="login_confirmations",
    )
    linked_account = models.ForeignKey(
        LinkedAccount,
        on_delete=models.CASCADE,
        related_name="confirmations",
        null=True, blank=True,
    )
    event = models.ForeignKey(
        ProviderLoginEvent,
        on_delete=models.SET_NULL,
        related_name="confirmations",
        null=True, blank=True,
    )
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default="pending")

    # Snapshot des infos device au moment de l'envoi (l'event peut être supprimé)
    ip_address = models.GenericIPAddressField(null=True, blank=True)
    browser = models.CharField(max_length=50, blank=True, default="")
    os = models.CharField(max_length=50, blank=True, default="")
    device_type = models.CharField(max_length=30, blank=True, default="")
    geo_city = models.CharField(max_length=120, blank=True, default="")
    geo_country = models.CharField(max_length=2, blank=True, default="")

    created_at = models.DateTimeField(auto_now_add=True)
    expires_at = models.DateTimeField()
    responded_at = models.DateTimeField(null=True, blank=True)
    responded_ip = models.GenericIPAddressField(null=True, blank=True)

    class Meta:
        verbose_name = "Confirmation de connexion"
        verbose_name_plural = "Confirmations de connexion"
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["user", "status"]),
            models.Index(fields=["status", "expires_at"]),
        ]

    def __str__(self):
        return f"Confirmation {self.status} — {self.user.email} @ {self.created_at:%Y-%m-%d %H:%M}"


# ─────────────────────────────────────────────────────────────────────────────
# SecurityNotification (persisté, alimente la cloche topbar)
# ─────────────────────────────────────────────────────────────────────────────


class SecurityNotification(models.Model):
    """
    Notification persistée de sécurité destinée à un utilisateur.

    À utiliser pour les alertes "compte lié" (brute force, nouveau device, etc.).
    Les alertes SOC globales (`apps.alerts.Alert`) restent gérées séparément.
    """

    LEVELS = [
        ("info", "Information"),
        ("warning", "Avertissement"),
        ("critical", "Critique"),
    ]

    KINDS = [
        ("login_new_device", "Nouvelle connexion (device inconnu)"),
        ("login_new_location", "Nouvelle connexion (lieu inconnu)"),
        ("impossible_travel", "Déplacement impossible"),
        ("brute_force", "Tentative de brute-force"),
        ("account_locked", "Compte verrouillé"),
        ("account_unlinked", "Compte délié"),
        ("provider_error", "Erreur provider"),
        ("info", "Information"),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="security_notifications",
    )
    kind = models.CharField(max_length=40, choices=KINDS)
    level = models.CharField(max_length=20, choices=LEVELS, default="info")
    title = models.CharField(max_length=200)
    body = models.TextField(blank=True, default="")

    linked_account = models.ForeignKey(
        LinkedAccount,
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name="notifications",
    )
    confirmation = models.ForeignKey(
        LoginConfirmation,
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name="notifications",
    )

    metadata = models.JSONField(default=dict, blank=True)
    is_read = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    read_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        verbose_name = "Notification sécurité"
        verbose_name_plural = "Notifications sécurité"
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["user", "is_read", "created_at"]),
            models.Index(fields=["kind", "created_at"]),
        ]

    def __str__(self):
        return f"[{self.level}] {self.title} — {self.user.email}"


# ─────────────────────────────────────────────────────────────────────────────
# AccountLinkVerification  (code PIN 4 chiffres, 5 minutes)
# ─────────────────────────────────────────────────────────────────────────────


class AccountLinkVerification(models.Model):
    """
    Vérification par code PIN 4 chiffres envoyé à l'email du provider.
    Créé après le callback OAuth, avant la création définitive du LinkedAccount.
    L'utilisateur entre le PIN reçu pour prouver qu'il possède ce compte.
    """

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="link_verifications",
    )
    provider = models.CharField(max_length=20)
    provider_email = models.EmailField()
    provider_user_id = models.CharField(max_length=255)
    provider_display_name = models.CharField(max_length=255, blank=True, default="")
    avatar_url = models.CharField(max_length=512, blank=True, default="")
    # Données OAuth serialisées (tokens chiffrés + scopes) pour finaliser la liaison
    oauth_data = models.JSONField(default=dict)
    pin = models.CharField(max_length=4)
    is_used = models.BooleanField(default=False)
    expires_at = models.DateTimeField()
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "Vérification de liaison"
        verbose_name_plural = "Vérifications de liaison"
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["user", "is_used", "expires_at"]),
        ]

    @property
    def is_valid(self) -> bool:
        from django.utils import timezone
        return not self.is_used and self.expires_at > timezone.now()

    def __str__(self):
        return f"PIN {self.provider}:{self.provider_email} — {self.user.email}"
