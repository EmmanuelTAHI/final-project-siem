"""
SOAR-lite — Playbooks de réponse automatisée aux incidents.
"""
import uuid

from django.db import models


class Playbook(models.Model):
    TRIGGER_TYPES = [
        ("severity", "Seuil de sévérité"),
        ("rule_match", "Règle de corrélation"),
        ("ml_anomaly", "Anomalie ML"),
        ("cti_match", "Correspondance CTI"),
        ("manual", "Manuel"),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    organization = models.ForeignKey(
        "organizations.Organization",
        on_delete=models.CASCADE,
        related_name="playbooks",
        verbose_name="Organisation",
    )
    name = models.CharField(max_length=200)
    description = models.TextField(blank=True)
    trigger_type = models.CharField(max_length=30, choices=TRIGGER_TYPES, default="severity")
    trigger_conditions = models.JSONField(
        default=dict,
        help_text="Ex: {severity: ['critical','high'], rule_ids: [...]}",
    )
    actions = models.JSONField(
        default=list,
        help_text="Liste d'actions: [{type: 'send_email', params: {...}}, ...]",
    )
    is_active = models.BooleanField(default=True, db_index=True)
    execution_count = models.PositiveIntegerField(default=0)
    created_by = models.ForeignKey(
        "users.User",
        on_delete=models.SET_NULL,
        null=True,
        related_name="playbooks",
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["name"]
        constraints = [
            models.UniqueConstraint(
                fields=["organization", "name"], name="unique_playbook_name_per_org"
            )
        ]

    def __str__(self):
        return self.name


class PlaybookExecution(models.Model):
    STATUS_CHOICES = [
        ("pending", "En attente"),
        ("running", "En cours"),
        ("success", "Succès"),
        ("partial", "Partiel"),
        ("failed", "Échoué"),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    organization = models.ForeignKey(
        "organizations.Organization",
        on_delete=models.CASCADE,
        related_name="playbook_executions",
        verbose_name="Organisation",
        help_text="Dénormalisé depuis playbook.organization pour l'isolation multi-tenant.",
    )
    playbook = models.ForeignKey(
        Playbook,
        on_delete=models.CASCADE,
        related_name="executions",
    )
    alert = models.ForeignKey(
        "alerts.Alert",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="playbook_executions",
    )
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default="pending", db_index=True)
    actions_taken = models.JSONField(default=list)
    error_message = models.TextField(blank=True)
    triggered_by = models.CharField(max_length=50, default="automatic")
    started_at = models.DateTimeField(auto_now_add=True)
    finished_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["-started_at"]

    def save(self, *args, **kwargs):
        if self.playbook_id and not self.organization_id:
            self.organization_id = self.playbook.organization_id
        super().save(*args, **kwargs)

    @property
    def duration_seconds(self):
        if self.finished_at and self.started_at:
            return (self.finished_at - self.started_at).total_seconds()
        return None
