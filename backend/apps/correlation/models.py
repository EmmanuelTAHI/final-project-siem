"""
Modèles du moteur de corrélation.
CorrelationRule : règles de détection.
RuleMatch : résultats des correspondances.
"""
import uuid

from django.db import models

from apps.users.models import User


class CorrelationRule(models.Model):
    """
    Règle de corrélation définissant une condition de détection d'anomalie.
    condition_logic est un JSONField décrivant la logique de détection.
    """

    SEVERITY_CHOICES = [
        ("low", "Faible"),
        ("medium", "Moyen"),
        ("high", "Élevé"),
        ("critical", "Critique"),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    organization = models.ForeignKey(
        "organizations.Organization",
        on_delete=models.CASCADE,
        related_name="correlation_rules",
        verbose_name="Organisation",
    )
    name = models.CharField(max_length=255, verbose_name="Nom de la règle")
    description = models.TextField(verbose_name="Description")
    is_active = models.BooleanField(default=True, verbose_name="Active")
    severity = models.CharField(
        max_length=20,
        choices=SEVERITY_CHOICES,
        verbose_name="Sévérité",
    )
    condition_logic = models.JSONField(
        verbose_name="Logique de condition",
        help_text=(
            "Ex: {'type': 'threshold', 'field': 'user_email', "
            "'action': 'login_failure', 'count': 5, 'window_seconds': 300}"
        ),
    )
    alert_title_template = models.CharField(
        max_length=500,
        verbose_name="Template de titre d'alerte",
        help_text="Ex: Brute force détecté sur {user_email}",
    )
    mitre_tactic = models.CharField(
        max_length=100,
        null=True,
        blank=True,
        verbose_name="MITRE Tactic",
    )
    mitre_technique = models.CharField(
        max_length=200,
        null=True,
        blank=True,
        verbose_name="MITRE Technique",
    )
    compliance_controls = models.JSONField(
        default=list,
        blank=True,
        verbose_name="Contrôles de conformité couverts",
        help_text="Ex: ['iso27001:A.5.15', 'pci_dss:REQ-10', 'nist_csf:PR.AC-1']",
    )
    created_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="correlation_rules",
        verbose_name="Créé par",
    )
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="Créé le")
    updated_at = models.DateTimeField(auto_now=True, verbose_name="Modifié le")

    class Meta:
        verbose_name = "Règle de corrélation"
        verbose_name_plural = "Règles de corrélation"
        ordering = ["name"]
        constraints = [
            models.UniqueConstraint(
                fields=["organization", "name"], name="unique_rule_name_per_org"
            )
        ]

    def __str__(self):
        status = "✓" if self.is_active else "✗"
        return f"[{status}] {self.name} ({self.severity})"


class RuleMatch(models.Model):
    """
    Enregistrement d'une correspondance de règle de corrélation.
    Référence les logs qui ont déclenché la règle et l'alerte générée.
    """

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    organization = models.ForeignKey(
        "organizations.Organization",
        on_delete=models.CASCADE,
        related_name="rule_matches",
        verbose_name="Organisation",
        help_text="Dénormalisé depuis rule.organization pour l'isolation multi-tenant.",
    )
    rule = models.ForeignKey(
        CorrelationRule,
        on_delete=models.CASCADE,
        related_name="matches",
        verbose_name="Règle",
    )
    logs = models.ManyToManyField(
        "logs.NormalizedLog",
        blank=True,
        related_name="rule_matches",
        verbose_name="Logs déclencheurs",
    )
    alert = models.ForeignKey(
        "alerts.Alert",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="rule_matches",
        verbose_name="Alerte générée",
    )
    matched_at = models.DateTimeField(auto_now_add=True, verbose_name="Correspondance le")

    class Meta:
        verbose_name = "Correspondance de règle"
        verbose_name_plural = "Correspondances de règles"
        ordering = ["-matched_at"]

    def save(self, *args, **kwargs):
        if self.rule_id and not self.organization_id:
            self.organization_id = self.rule.organization_id
        super().save(*args, **kwargs)

    def __str__(self):
        return f"Match: {self.rule.name} → Alert {self.alert_id or 'N/A'} @ {self.matched_at:%Y-%m-%d %H:%M}"
