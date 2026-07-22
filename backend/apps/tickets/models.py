"""
Ticketing SOC — création d'incidents à partir d'une alerte ou en libre,
suivi de statut/priorité/assignation, commentaires et historique d'activité.
Modèle inspiré des systèmes de ticketing de référence (Jira Service Mgmt,
ServiceNow, Splunk SOAR case management).
"""
import uuid

from django.db import models

from apps.users.models import User


class Ticket(models.Model):
    """
    Ticket SOC : incident/tâche de suivi, éventuellement rattaché à une
    alerte (mais peut aussi exister seul, ex: demande, tâche de suivi).
    Cycle de vie : open → in_progress → pending → resolved → closed
    (pending = en attente d'une action externe, ex: réponse utilisateur).
    """

    STATUS_CHOICES = [
        ("open", "Ouvert"),
        ("in_progress", "En cours"),
        ("pending", "En attente"),
        ("resolved", "Résolu"),
        ("closed", "Fermé"),
    ]
    OPEN_STATUSES = ("open", "in_progress", "pending")
    CLOSED_STATUSES = ("resolved", "closed")

    PRIORITY_CHOICES = [
        ("low", "Faible"),
        ("medium", "Moyen"),
        ("high", "Élevé"),
        ("critical", "Critique"),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    organization = models.ForeignKey(
        "organizations.Organization",
        on_delete=models.CASCADE,
        related_name="tickets",
        verbose_name="Organisation",
    )
    # Numéro lisible par organisation (TCK-1, TCK-2...) — façon Jira/ServiceNow,
    # bien plus pratique à référencer à l'oral/dans un rapport qu'un UUID.
    number = models.PositiveIntegerField(editable=False, verbose_name="Numéro")

    title = models.CharField(max_length=300, verbose_name="Titre")
    description = models.TextField(blank=True, default="", verbose_name="Description")

    status = models.CharField(
        max_length=20, choices=STATUS_CHOICES, default="open", db_index=True, verbose_name="Statut",
    )
    priority = models.CharField(
        max_length=20, choices=PRIORITY_CHOICES, default="medium", db_index=True, verbose_name="Priorité",
    )

    alert = models.ForeignKey(
        "alerts.Alert",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="tickets",
        verbose_name="Alerte liée",
    )
    # Agrégation multi-alertes (case management) : un incident réel implique
    # souvent plusieurs alertes corrélées (ex: brute force + impossible
    # travel sur le même compte). `alert` reste la relation "principale"
    # (rétrocompatibilité), `linked_alerts` permet de regrouper tout un
    # scénario d'incident sur un seul ticket.
    linked_alerts = models.ManyToManyField(
        "alerts.Alert",
        blank=True,
        related_name="linked_tickets",
        verbose_name="Alertes associées",
    )
    reporter = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="reported_tickets",
        verbose_name="Rapporté par",
    )
    assignee = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="assigned_tickets",
        verbose_name="Assigné à",
    )

    due_date = models.DateTimeField(null=True, blank=True, verbose_name="Échéance")
    resolution_note = models.TextField(null=True, blank=True, verbose_name="Note de résolution")

    created_at = models.DateTimeField(auto_now_add=True, db_index=True, verbose_name="Créé le")
    updated_at = models.DateTimeField(auto_now=True, verbose_name="Modifié le")
    resolved_at = models.DateTimeField(null=True, blank=True, verbose_name="Résolu le")
    closed_at = models.DateTimeField(null=True, blank=True, verbose_name="Fermé le")

    class Meta:
        verbose_name = "Ticket"
        verbose_name_plural = "Tickets"
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["organization", "status"]),
            models.Index(fields=["organization", "number"]),
            models.Index(fields=["assignee", "status"]),
        ]
        constraints = [
            models.UniqueConstraint(fields=["organization", "number"], name="unique_ticket_number_per_org"),
        ]

    def __str__(self):
        return f"TCK-{self.number} · {self.title[:60]} [{self.status}]"

    @property
    def display_id(self) -> str:
        return f"TCK-{self.number}"

    @property
    def is_overdue(self) -> bool:
        if not self.due_date or self.status in self.CLOSED_STATUSES:
            return False
        from django.utils import timezone
        return self.due_date < timezone.now()


class TicketComment(models.Model):
    """Commentaire d'analyste sur un ticket."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    ticket = models.ForeignKey(Ticket, on_delete=models.CASCADE, related_name="comments", verbose_name="Ticket")
    author = models.ForeignKey(
        User, on_delete=models.SET_NULL, null=True, blank=True, related_name="ticket_comments", verbose_name="Auteur",
    )
    content = models.TextField(verbose_name="Contenu")
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="Créé le")

    class Meta:
        verbose_name = "Commentaire de ticket"
        verbose_name_plural = "Commentaires de tickets"
        ordering = ["created_at"]

    def __str__(self):
        author_str = self.author.email if self.author else "Système"
        return f"Commentaire [{author_str}] sur {self.ticket.display_id}"


class TicketActivity(models.Model):
    """
    Historique d'activité d'un ticket (timeline façon Jira/ServiceNow) :
    création, changement de statut/priorité/assignation, commentaire.
    Distinct du AuditTrail global (apps.users) pour offrir une timeline
    dédiée et structurée (from_value/to_value) directement exploitable par
    le panneau de détail du ticket, sans dépendre du format générique
    `extra_data` de l'audit trail plateforme.
    """

    ACTION_CHOICES = [
        ("created", "Création"),
        ("status_changed", "Changement de statut"),
        ("priority_changed", "Changement de priorité"),
        ("assigned", "Assignation"),
        ("commented", "Commentaire"),
        ("updated", "Mise à jour"),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    ticket = models.ForeignKey(Ticket, on_delete=models.CASCADE, related_name="activities", verbose_name="Ticket")
    actor = models.ForeignKey(
        User, on_delete=models.SET_NULL, null=True, blank=True, related_name="ticket_activities", verbose_name="Auteur",
    )
    action = models.CharField(max_length=30, choices=ACTION_CHOICES, verbose_name="Action")
    from_value = models.CharField(max_length=255, blank=True, default="", verbose_name="Ancienne valeur")
    to_value = models.CharField(max_length=255, blank=True, default="", verbose_name="Nouvelle valeur")
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="Créé le")

    class Meta:
        verbose_name = "Activité de ticket"
        verbose_name_plural = "Activités de tickets"
        ordering = ["created_at"]

    def __str__(self):
        return f"{self.get_action_display()} sur {self.ticket.display_id}"
