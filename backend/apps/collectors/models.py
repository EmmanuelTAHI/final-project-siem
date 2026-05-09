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
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
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

    def __str__(self):
        return f"Job {self.id} — {self.connector.name} [{self.status}]"

    @property
    def duration_seconds(self) -> float | None:
        """Durée du job en secondes."""
        if self.started_at and self.finished_at:
            return (self.finished_at - self.started_at).total_seconds()
        return None
