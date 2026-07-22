"""
Action SOAR : crée un ticket Argus natif (apps.tickets.Ticket) rattaché à
l'alerte déclenchante — contrairement à `create_ticket.py` (qui parle à un
ITSM externe type Jira/ServiceNow), celle-ci alimente directement le
case management interne d'Argus, visible immédiatement dans /tickets.
"""
import logging

from django.db import transaction

logger = logging.getLogger(__name__)

_SEVERITY_TO_PRIORITY = {
    "critical": "critical",
    "high": "high",
    "medium": "medium",
    "low": "low",
}


def execute(params: dict, alert) -> dict:
    """
    params: {
        title_template: "Incident SOC : {title}",  # optionnel
        priority: "critical",  # optionnel, sinon dérivé de la sévérité de l'alerte
    }
    """
    from apps.tickets.models import Ticket, TicketActivity

    title_template = params.get("title_template") or "Incident SOC : {title}"
    priority = params.get("priority") or _SEVERITY_TO_PRIORITY.get(alert.severity, "medium")

    existing = Ticket.objects.filter(alert=alert).first()
    if existing:
        return {"status": "skipped", "reason": "ticket_already_exists", "ticket_id": str(existing.id), "display_id": existing.display_id}

    with transaction.atomic():
        last = (
            Ticket.objects.select_for_update()
            .filter(organization=alert.organization)
            .order_by("-number")
            .first()
        )
        next_number = (last.number + 1) if last else 1

        ticket = Ticket.objects.create(
            organization=alert.organization,
            number=next_number,
            title=title_template.format(title=alert.title),
            description=alert.description,
            priority=priority,
            status="open",
            alert=alert,
        )
        ticket.linked_alerts.add(alert)
        TicketActivity.objects.create(
            ticket=ticket, action="created", to_value="Ouvert (créé automatiquement par SOAR)",
        )

    logger.info("SOAR create_internal_ticket: %s créé pour alerte %s", ticket.display_id, alert.id)
    return {"status": "success", "ticket_id": str(ticket.id), "display_id": ticket.display_id}
