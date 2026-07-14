"""
Threat Intelligence — modèles pour les indicateurs de compromission (IoC).
"""
import uuid

from django.db import models
from django.utils import timezone


class ThreatIndicator(models.Model):
    INDICATOR_TYPES = [
        ("ip", "Adresse IP"),
        ("domain", "Domaine"),
        ("hash_md5", "Hash MD5"),
        ("hash_sha256", "Hash SHA256"),
        ("url", "URL"),
        ("email", "Email"),
    ]

    SOURCES = [
        ("abuseipdb", "AbuseIPDB"),
        ("virustotal", "VirusTotal"),
        ("manual", "Manuel"),
        ("otx", "AlienVault OTX"),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    indicator_type = models.CharField(max_length=20, choices=INDICATOR_TYPES, db_index=True)
    value = models.CharField(max_length=512, db_index=True)
    reputation_score = models.FloatField(default=0.0, help_text="0.0 (safe) à 100.0 (malicious)")
    confidence = models.FloatField(default=0.0, help_text="0.0 à 1.0")
    source = models.CharField(max_length=30, choices=SOURCES, default="abuseipdb")
    tags = models.JSONField(default=list, blank=True)
    raw_data = models.JSONField(default=dict, blank=True)
    is_malicious = models.BooleanField(default=False, db_index=True)
    last_seen = models.DateTimeField(default=timezone.now)
    first_seen = models.DateTimeField(default=timezone.now)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        unique_together = [("indicator_type", "value", "source")]
        indexes = [
            models.Index(fields=["indicator_type", "is_malicious"]),
            models.Index(fields=["reputation_score"]),
        ]
        ordering = ["-reputation_score"]

    def __str__(self):
        return f"[{self.indicator_type}] {self.value} — score={self.reputation_score:.1f}"


class EnrichedLog(models.Model):
    """Liaison entre un NormalizedLog et ses indicateurs CTI."""
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    organization = models.ForeignKey(
        "organizations.Organization",
        on_delete=models.CASCADE,
        related_name="enriched_logs",
        verbose_name="Organisation",
        help_text="Dénormalisé depuis log.organization pour l'isolation multi-tenant.",
    )
    log = models.OneToOneField(
        "logs.NormalizedLog",
        on_delete=models.CASCADE,
        related_name="cti_enrichment",
    )
    indicators = models.ManyToManyField(ThreatIndicator, blank=True)
    max_score = models.FloatField(default=0.0)
    is_threat = models.BooleanField(default=False, db_index=True)
    enriched_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-enriched_at"]

    def save(self, *args, **kwargs):
        if self.log_id and not self.organization_id:
            self.organization_id = self.log.organization_id
        super().save(*args, **kwargs)

    def compute_max_score(self):
        agg = self.indicators.aggregate(models.Max("reputation_score"))
        self.max_score = agg["reputation_score__max"] or 0.0
        self.is_threat = self.max_score >= 50.0
        self.save(update_fields=["max_score", "is_threat"])
