"""
Modèles pour les connecteurs de collecte de logs.
ConnectorConfig stocke la configuration chiffrée de chaque source.
CollectionJob trace l'historique de chaque collecte.
"""
import uuid

from django.db import models

from apps.users.models import User


class ConnectorConfig(models.Model):
    """
    Configuration d'un connecteur de source de logs.
    Les credentials et tokens OAuth2 sont chiffrés avec Fernet AES-256.
    """

    SOURCE_TYPE_CHOICES = [
        ("microsoft365", "Microsoft 365"),
        ("google_workspace", "Google Workspace"),
        ("wazuh", "Wazuh SIEM"),
        ("syslog", "Syslog"),
        ("agent", "Agent Log+ (HTTP authentifié)"),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    organization = models.ForeignKey(
        "organizations.Organization",
        on_delete=models.CASCADE,
        related_name="connectors",
        verbose_name="Organisation",
    )
    name = models.CharField(max_length=255, verbose_name="Nom du connecteur")
    source_type = models.CharField(
        max_length=50,
        choices=SOURCE_TYPE_CHOICES,
        verbose_name="Type de source",
    )
    # JSON chiffré avec Fernet : {"client_id", "client_secret", "tenant_id", "scopes"}
    credentials_encrypted = models.TextField(
        blank=True,
        default="",
        verbose_name="Credentials chiffrés (Fernet)",
    )
    # Tokens OAuth2 chiffrés
    oauth_access_token = models.TextField(
        null=True,
        blank=True,
        verbose_name="Access Token OAuth2 (chiffré)",
    )
    oauth_refresh_token = models.TextField(
        null=True,
        blank=True,
        verbose_name="Refresh Token OAuth2 (chiffré)",
    )
    token_expires_at = models.DateTimeField(
        null=True,
        blank=True,
        verbose_name="Expiration du token",
    )
    is_active = models.BooleanField(default=True, verbose_name="Actif")
    polling_interval_seconds = models.IntegerField(
        default=300,
        verbose_name="Intervalle de collecte (secondes)",
    )
    last_collected_at = models.DateTimeField(
        null=True,
        blank=True,
        verbose_name="Dernière collecte",
    )
    allowed_source_ips = models.JSONField(
        default=list,
        blank=True,
        verbose_name="Adresses IP autorisées (mode syslog UDP self-host uniquement)",
        help_text=(
            "Liste d'IP/CIDR autorisées à pousser du syslog UDP vers ce connecteur. "
            "Non utilisé par l'ingestion HTTP authentifiée par token (agents)."
        ),
    )
    created_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="connectors",
        verbose_name="Créé par",
    )
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="Créé le")

    class Meta:
        verbose_name = "Connecteur"
        verbose_name_plural = "Connecteurs"
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.name} [{self.get_source_type_display()}] {'✓' if self.is_active else '✗'}"

    def get_credentials(self) -> dict:
        """Déchiffre et retourne les credentials."""
        from utils.encryption import decrypt_dict
        if not self.credentials_encrypted:
            return {}
        return decrypt_dict(self.credentials_encrypted)

    def set_credentials(self, credentials: dict) -> None:
        """Chiffre et stocke les credentials."""
        from utils.encryption import encrypt_dict
        self.credentials_encrypted = encrypt_dict(credentials)


class CollectionJob(models.Model):
    """
    Historique des jobs de collecte Celery.
    Trace le statut, le nombre de logs collectés et les erreurs.
    """

    STATUS_CHOICES = [
        ("pending", "En attente"),
        ("running", "En cours"),
        ("success", "Succès"),
        ("failed", "Échoué"),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    connector = models.ForeignKey(
        ConnectorConfig,
        on_delete=models.CASCADE,
        related_name="jobs",
        verbose_name="Connecteur",
    )
    organization = models.ForeignKey(
        "organizations.Organization",
        on_delete=models.CASCADE,
        related_name="collection_jobs",
        verbose_name="Organisation",
        help_text="Dénormalisé depuis connector.organization pour l'isolation multi-tenant.",
    )
    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default="pending",
        verbose_name="Statut",
    )
    logs_collected_count = models.IntegerField(
        default=0,
        verbose_name="Logs collectés",
    )
    error_message = models.TextField(
        null=True,
        blank=True,
        verbose_name="Message d'erreur",
    )
    started_at = models.DateTimeField(null=True, blank=True, verbose_name="Démarré le")
    finished_at = models.DateTimeField(null=True, blank=True, verbose_name="Terminé le")

    class Meta:
        verbose_name = "Job de collecte"
        verbose_name_plural = "Jobs de collecte"
        ordering = ["-started_at"]
        indexes = [
            models.Index(fields=["connector", "status"]),
            models.Index(fields=["started_at"]),
        ]

    def save(self, *args, **kwargs):
        if self.connector_id and not self.organization_id:
            self.organization_id = self.connector.organization_id
        super().save(*args, **kwargs)

    def __str__(self):
        return f"Job {self.id} — {self.connector.name} [{self.status}]"

    @property
    def duration_seconds(self) -> float | None:
        """Durée du job en secondes."""
        if self.started_at and self.finished_at:
            return (self.finished_at - self.started_at).total_seconds()
        return None


class AgentEnrollmentToken(models.Model):
    """
    Token bearer permettant à un agent de collecte (rsyslog, NXLog, Fluent
    Bit...) déployé chez une organisation de pousser des logs vers
    /api/ingest/agent/logs/. Stocké en hash (jamais réversible) — c'est un
    secret bearer vérifié à chaque requête, pas une donnée à relire.

    Le token brut n'est renvoyé qu'une seule fois à la création (voir
    AgentEnrollmentTokenViewSet), jamais stocké en clair.
    """

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    organization = models.ForeignKey(
        "organizations.Organization",
        on_delete=models.CASCADE,
        related_name="enrollment_tokens",
        verbose_name="Organisation",
    )
    name = models.CharField(
        max_length=200,
        verbose_name="Nom",
        help_text="Ex: « Serveurs web prod », « Parc Windows siège »",
    )
    token_prefix = models.CharField(max_length=8, db_index=True, verbose_name="Préfixe (lookup rapide)")
    token_hash = models.CharField(max_length=64, verbose_name="Hash SHA-256 du token")
    connector = models.ForeignKey(
        ConnectorConfig,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="enrollment_tokens",
        verbose_name="Connecteur associé",
        help_text="Créé/lié automatiquement au premier usage du token.",
    )
    created_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="enrollment_tokens",
        verbose_name="Créé par",
    )
    is_active = models.BooleanField(default=True, verbose_name="Actif")
    last_used_at = models.DateTimeField(null=True, blank=True, verbose_name="Dernier usage")
    last_used_ip = models.GenericIPAddressField(null=True, blank=True, verbose_name="Dernière IP")
    expires_at = models.DateTimeField(null=True, blank=True, verbose_name="Expiration")
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="Créé le")

    class Meta:
        verbose_name = "Token d'enrôlement d'agent"
        verbose_name_plural = "Tokens d'enrôlement d'agents"
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["token_prefix", "is_active"]),
        ]

    def __str__(self):
        return f"{self.name} [{self.organization.name}] {'✓' if self.is_active else '✗'}"
