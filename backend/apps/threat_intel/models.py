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
        ("urlhaus", "abuse.ch URLhaus (communautaire)"),
        ("feodotracker", "abuse.ch Feodo Tracker (communautaire)"),
        ("federation", "Réseau collaboratif Argus (instances fédérées)"),
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


class CVERecord(models.Model):
    """
    Référentiel de vulnérabilités connues, synchronisé automatiquement depuis
    des sources publiques (NVD, CISA KEV). Table globale (pas de FK
    organization) : une CVE existe indépendamment des organisations, comme
    ThreatIndicator. C'est ce référentiel qui permet à Argus de savoir
    qu'une vulnérabilité vient d'être découverte AVANT qu'un incident ne se
    produise, contrairement à une détection purement réactive basée sur des
    règles écrites à la main.
    """

    SEVERITY_CHOICES = [
        ("low", "Faible"),
        ("medium", "Moyen"),
        ("high", "Élevé"),
        ("critical", "Critique"),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    cve_id = models.CharField(max_length=32, unique=True, db_index=True, verbose_name="Identifiant CVE")
    description = models.TextField(blank=True, verbose_name="Description")
    cvss_score = models.FloatField(null=True, blank=True, verbose_name="Score CVSS")
    severity = models.CharField(max_length=20, choices=SEVERITY_CHOICES, blank=True, db_index=True)
    vendor_project = models.CharField(max_length=255, blank=True, db_index=True, verbose_name="Éditeur")
    product = models.CharField(max_length=255, blank=True, db_index=True, verbose_name="Produit")
    published_date = models.DateTimeField(null=True, blank=True)
    modified_date = models.DateTimeField(null=True, blank=True)

    # Champs CISA KEV (Known Exploited Vulnerabilities) — le point clé : une
    # CVE marquée is_kev=True est EXPLOITÉE ACTIVEMENT dans la nature, pas
    # juste théorique. C'est le signal de priorisation le plus fort qui
    # existe en threat intel gratuite.
    is_kev = models.BooleanField(default=False, db_index=True, verbose_name="Exploitée activement (CISA KEV)")
    kev_date_added = models.DateTimeField(null=True, blank=True)
    kev_due_date = models.DateTimeField(null=True, blank=True)
    kev_ransomware_use = models.BooleanField(default=False, verbose_name="Utilisée par des ransomwares connus")
    kev_required_action = models.TextField(blank=True)

    raw_data = models.JSONField(default=dict, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-is_kev", "-cvss_score", "-published_date"]
        indexes = [
            models.Index(fields=["is_kev", "severity"]),
            models.Index(fields=["vendor_project", "product"]),
        ]

    def __str__(self):
        return f"{self.cve_id} (CVSS {self.cvss_score or '?'}, KEV={self.is_kev})"


class Asset(models.Model):
    """
    Inventaire logiciel/matériel d'une organisation. Alimenté manuellement
    (formulaire) ou automatiquement (best-effort, ex. extraction depuis
    NormalizedLog.extra_fields/user_agent par les collecteurs). Sert de base
    à la corrélation CVE ↔ actif exposé.
    """

    ASSET_TYPES = [
        ("server", "Serveur"),
        ("workstation", "Poste de travail"),
        ("network_device", "Équipement réseau"),
        ("application", "Application"),
        ("cloud_service", "Service cloud"),
        ("other", "Autre"),
    ]

    CRITICALITY_CHOICES = [
        ("low", "Faible"),
        ("medium", "Moyen"),
        ("high", "Élevé"),
        ("critical", "Critique"),
    ]

    SOURCE_CHOICES = [
        ("manual", "Saisie manuelle"),
        ("auto_detected", "Détection automatique"),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    organization = models.ForeignKey(
        "organizations.Organization", on_delete=models.CASCADE, related_name="assets",
    )
    name = models.CharField(max_length=255, verbose_name="Nom de l'actif")
    asset_type = models.CharField(max_length=30, choices=ASSET_TYPES, default="server")
    vendor = models.CharField(max_length=255, blank=True, verbose_name="Éditeur/Fabricant")
    product = models.CharField(max_length=255, blank=True, verbose_name="Produit")
    version = models.CharField(max_length=100, blank=True)
    hostname = models.CharField(max_length=255, blank=True)
    ip_address = models.GenericIPAddressField(null=True, blank=True)
    criticality = models.CharField(max_length=20, choices=CRITICALITY_CHOICES, default="medium")
    source = models.CharField(max_length=20, choices=SOURCE_CHOICES, default="manual")
    last_seen = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-criticality", "name"]
        indexes = [
            models.Index(fields=["organization", "vendor", "product"]),
        ]

    def __str__(self):
        return f"{self.name} ({self.vendor} {self.product} {self.version})".strip()


class AssetVulnerability(models.Model):
    """Liaison actif ↔ CVE : ce qu'Argus a détecté comme exposition réelle."""

    STATUS_CHOICES = [
        ("open", "Ouverte"),
        ("acknowledged", "Prise en compte"),
        ("mitigated", "Corrigée"),
        ("false_positive", "Faux positif"),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    organization = models.ForeignKey(
        "organizations.Organization", on_delete=models.CASCADE, related_name="asset_vulnerabilities",
    )
    asset = models.ForeignKey(Asset, on_delete=models.CASCADE, related_name="vulnerabilities")
    cve = models.ForeignKey(CVERecord, on_delete=models.CASCADE, related_name="affected_assets")
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default="open", db_index=True)
    matched_reason = models.CharField(max_length=255, blank=True)
    matched_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = [("asset", "cve")]
        ordering = ["-matched_at"]

    def save(self, *args, **kwargs):
        if self.asset_id and not self.organization_id:
            self.organization_id = self.asset.organization_id
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.asset.name} — {self.cve.cve_id} [{self.status}]"
