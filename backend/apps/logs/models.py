"""
Modèles de stockage des logs bruts et normalisés.
RawLog : payload brut de l'API source.
NormalizedLog : format inspiré CEF (Common Event Format).
"""
import uuid

from django.db import models

from apps.collectors.models import ConnectorConfig


class RawLog(models.Model):
    """
    Log brut tel que reçu depuis la source (Microsoft, Google, Wazuh...).
    Conservé pour l'audit et le re-traitement.
    """

    SOURCE_TYPE_CHOICES = [
        ("microsoft365", "Microsoft 365"),
        ("google_workspace", "Google Workspace"),
        ("wazuh", "Wazuh"),
        ("syslog", "Syslog"),
        ("agent", "Agent Argus (HTTP authentifié)"),
        ("manual", "Manuel"),
        ("argus", "Argus (plateforme)"),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    organization = models.ForeignKey(
        "organizations.Organization",
        on_delete=models.CASCADE,
        related_name="raw_logs",
        verbose_name="Organisation",
    )
    source_type = models.CharField(
        max_length=50,
        choices=SOURCE_TYPE_CHOICES,
        verbose_name="Type de source",
    )
    connector = models.ForeignKey(
        ConnectorConfig,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="raw_logs",
        verbose_name="Connecteur",
    )
    raw_data = models.JSONField(verbose_name="Données brutes")
    received_at = models.DateTimeField(auto_now_add=True, verbose_name="Reçu le")
    is_normalized = models.BooleanField(default=False, verbose_name="Normalisé")

    class Meta:
        verbose_name = "Log brut"
        verbose_name_plural = "Logs bruts"
        ordering = ["-received_at"]
        indexes = [
            models.Index(fields=["source_type", "received_at"]),
            models.Index(fields=["is_normalized"]),
            models.Index(fields=["connector"]),
            models.Index(fields=["organization", "received_at"]),
        ]

    def __str__(self):
        return f"RawLog [{self.source_type}] {self.received_at:%Y-%m-%d %H:%M:%S}"


class NormalizedLog(models.Model):
    """
    Log normalisé au format inspiré CEF (Common Event Format).
    Utilisé par le moteur de corrélation et le module ML.
    """

    OUTCOME_CHOICES = [
        ("success", "Succès"),
        ("failure", "Échec"),
        ("unknown", "Inconnu"),
    ]

    SEVERITY_CHOICES = [
        ("info", "Info"),
        ("low", "Faible"),
        ("medium", "Moyen"),
        ("high", "Élevé"),
        ("critical", "Critique"),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    organization = models.ForeignKey(
        "organizations.Organization",
        on_delete=models.CASCADE,
        related_name="normalized_logs",
        verbose_name="Organisation",
        help_text="Dénormalisé depuis raw_log.organization pour l'isolation multi-tenant.",
    )
    raw_log = models.OneToOneField(
        RawLog,
        on_delete=models.CASCADE,
        related_name="normalized",
        verbose_name="Log brut",
    )
    event_time = models.DateTimeField(verbose_name="Horodatage de l'événement", db_index=True)
    source_ip = models.GenericIPAddressField(
        null=True,
        blank=True,
        verbose_name="IP source",
    )
    destination_ip = models.GenericIPAddressField(
        null=True,
        blank=True,
        verbose_name="IP destination",
    )
    user_email = models.CharField(
        max_length=320,
        null=True,
        blank=True,
        verbose_name="Email utilisateur",
        db_index=True,
    )
    user_id = models.CharField(
        max_length=255,
        null=True,
        blank=True,
        verbose_name="ID utilisateur source",
    )
    action = models.CharField(
        max_length=100,
        verbose_name="Action",
        db_index=True,
        help_text="Ex: login_success, login_failure, file_download, privilege_change",
    )
    outcome = models.CharField(
        max_length=20,
        choices=OUTCOME_CHOICES,
        default="unknown",
        verbose_name="Résultat",
    )
    resource = models.CharField(
        max_length=500,
        null=True,
        blank=True,
        verbose_name="Ressource accédée",
    )
    geo_country = models.CharField(
        max_length=2,
        null=True,
        blank=True,
        verbose_name="Pays (ISO 3166-1 alpha-2)",
    )
    geo_city = models.CharField(
        max_length=100,
        null=True,
        blank=True,
        verbose_name="Ville",
    )
    geo_latitude = models.FloatField(null=True, blank=True, verbose_name="Latitude")
    geo_longitude = models.FloatField(null=True, blank=True, verbose_name="Longitude")
    user_agent = models.TextField(null=True, blank=True, verbose_name="User-Agent")
    severity = models.CharField(
        max_length=20,
        choices=SEVERITY_CHOICES,
        default="info",
        verbose_name="Sévérité",
        db_index=True,
    )
    source_type = models.CharField(
        max_length=50,
        verbose_name="Type de source",
        db_index=True,
    )
    extra_fields = models.JSONField(
        default=dict,
        blank=True,
        verbose_name="Champs supplémentaires",
    )
    indexed_at = models.DateTimeField(
        auto_now_add=True,
        verbose_name="Indexé le",
        db_index=True,
    )

    class Meta:
        verbose_name = "Log normalisé"
        verbose_name_plural = "Logs normalisés"
        ordering = ["-event_time"]
        indexes = [
            models.Index(fields=["source_type", "event_time"]),
            models.Index(fields=["user_email", "event_time"]),
            models.Index(fields=["action", "outcome"]),
            models.Index(fields=["geo_country"]),
            models.Index(fields=["severity", "event_time"]),
            models.Index(fields=["organization", "event_time"]),
        ]

    def save(self, *args, **kwargs):
        if self.raw_log_id and not self.organization_id:
            self.organization_id = self.raw_log.organization_id
        super().save(*args, **kwargs)

    def __str__(self):
        return (
            f"NormalizedLog [{self.source_type}] {self.action} "
            f"— {self.user_email or 'N/A'} — {self.event_time:%Y-%m-%d %H:%M:%S}"
        )
