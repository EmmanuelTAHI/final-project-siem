"""Historique des rapports générés (compliance, SOC, activité, personnalisés)."""
import uuid

from django.db import models


class GeneratedReport(models.Model):
    REPORT_TYPE_CHOICES = [
        ("soc_weekly", "Rapport hebdomadaire SOC"),
        ("iso27001", "Conformité ISO 27001"),
        ("gdpr", "Conformité RGPD"),
        ("pci_dss", "Conformité PCI DSS"),
        ("top_threats", "Top menaces détectées"),
        ("user_activity", "Activité utilisateurs"),
        ("custom", "Rapport personnalisé"),
    ]
    FORMAT_CHOICES = [("pdf", "PDF"), ("csv", "CSV"), ("json", "JSON")]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    organization = models.ForeignKey(
        "organizations.Organization",
        on_delete=models.CASCADE,
        related_name="generated_reports",
        verbose_name="Organisation",
    )
    requested_by = models.ForeignKey(
        "users.User",
        on_delete=models.SET_NULL,
        null=True,
        related_name="generated_reports",
        verbose_name="Demandé par",
    )
    report_type = models.CharField(max_length=30, choices=REPORT_TYPE_CHOICES, verbose_name="Type")
    label = models.CharField(max_length=255, verbose_name="Libellé")
    format = models.CharField(max_length=10, choices=FORMAT_CHOICES, default="pdf", verbose_name="Format")
    period_days = models.PositiveIntegerField(default=30, verbose_name="Période (jours)")
    file = models.FileField(upload_to="reports/%Y/%m/", verbose_name="Fichier")
    file_size = models.PositiveIntegerField(default=0, verbose_name="Taille (octets)")
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="Généré le")

    class Meta:
        verbose_name = "Rapport généré"
        verbose_name_plural = "Rapports générés"
        ordering = ["-created_at"]
        indexes = [models.Index(fields=["organization", "-created_at"])]

    def __str__(self):
        return f"{self.label} [{self.format}] {self.created_at:%Y-%m-%d %H:%M}"
