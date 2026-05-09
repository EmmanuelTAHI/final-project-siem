"""
Modèles de gestion des alertes SOC.
Alert, AlertComment.
"""
import uuid

from django.db import models

from apps.users.models import User


class Alert(models.Model):
    """
    Alerte de sécurité générée par le moteur de corrélation ou le module ML.
    Cycle de vie : open → in_progress → resolved | false_positive
    """

    SEVERITY_CHOICES = [
        ("low", "Faible"),
        ("medium", "Moyen"),
        ("high", "Élevé"),
        ("critical", "Critique"),
    ]

    STATUS_CHOICES = [
        ("open", "Ouverte"),
        ("in_progress", "En cours"),
        ("resolved", "Résolue"),
        ("false_positive", "Faux positif"),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    title = models.CharField(max_length=500, verbose_name="Titre")
    description = models.TextField(verbose_name="Description")
    severity = models.CharField(
        max_length=20,
        choices=SEVERITY_CHOICES,
        verbose_name="Sévérité",
        db_index=True,
    )
    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default="open",
        verbose_name="Statut",
        db_index=True,
    )
    rule = models.ForeignKey(
        "correlation.CorrelationRule",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="alerts",
        verbose_name="Règle déclencheuse",
    )
    assigned_to = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="assigned_alerts",
        verbose_name="Assignée à",
    )
    source_logs = models.ManyToManyField(
        "logs.NormalizedLog",
        blank=True,
        related_name="alerts",
        verbose_name="Logs sources",
    )
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="Créée le", db_index=True)
    updated_at = models.DateTimeField(auto_now=True, verbose_name="Modifiée le")
    resolved_at = models.DateTimeField(null=True, blank=True, verbose_name="Résolue le")
    resolution_note = models.TextField(null=True, blank=True, verbose_name="Note de résolution")

    class Meta:
        verbose_name = "Alerte"
        verbose_name_plural = "Alertes"
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["severity", "status"]),
            models.Index(fields=["status", "created_at"]),
            models.Index(fields=["assigned_to", "status"]),
        ]

    def __str__(self):
        return f"[{self.severity.upper()}] {self.title} [{self.status}]"

    @property
    def time_to_resolve_hours(self) -> float | None:
        """Durée de résolution en heures (si résolue)."""
        if self.resolved_at and self.created_at:
            return round((self.resolved_at - self.created_at).total_seconds() / 3600, 2)
        return None

    def resolve(self, user, note: str = "") -> None:
        """Résout l'alerte et enregistre la note."""
        from django.utils import timezone
        self.status = "resolved"
        self.resolved_at = timezone.now()
        self.resolution_note = note
        self.save(update_fields=["status", "resolved_at", "resolution_note", "updated_at"])
        from apps.users.models import AuditTrail
        AuditTrail.log(
            action="alert_resolve",
            user=user,
            target_model="Alert",
            target_id=self.id,
            extra_data={"note": note[:500] if note else ""},
        )


class AlertComment(models.Model):
    """
    Commentaire d'analyste SOC sur une alerte.
    """

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    alert = models.ForeignKey(
        Alert,
        on_delete=models.CASCADE,
        related_name="comments",
        verbose_name="Alerte",
    )
    author = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="alert_comments",
        verbose_name="Auteur",
    )
    content = models.TextField(verbose_name="Contenu")
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="Créé le")

    class Meta:
        verbose_name = "Commentaire d'alerte"
        verbose_name_plural = "Commentaires d'alertes"
        ordering = ["created_at"]

    def __str__(self):
        author_str = self.author.email if self.author else "Système"
        return f"Commentaire [{author_str}] sur {self.alert.title[:50]}"
