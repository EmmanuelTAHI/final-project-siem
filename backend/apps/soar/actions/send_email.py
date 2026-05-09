"""Action SOAR : envoi d'email de notification SOC."""
import logging

from django.conf import settings
from django.core.mail import send_mail

logger = logging.getLogger(__name__)


def execute(params: dict, alert) -> dict:
    """
    params: {recipients: [...], subject_template: "...", body_template: "..."}
    """
    recipients = params.get("recipients", [])
    if not recipients:
        return {"status": "skipped", "reason": "no_recipients"}

    subject = params.get("subject_template", "Alerte Log+ : {title}").format(
        title=alert.title, severity=alert.severity.upper()
    )
    body = params.get(
        "body_template",
        "Alerte détectée : {title}\nSévérité : {severity}\nStatut : {status}\nCréée le : {created_at}",
    ).format(
        title=alert.title,
        severity=alert.severity.upper(),
        status=alert.status,
        created_at=alert.created_at.strftime("%Y-%m-%d %H:%M UTC"),
    )

    try:
        send_mail(
            subject=subject,
            message=body,
            from_email=getattr(settings, "DEFAULT_FROM_EMAIL", "noreply@logplus.ci"),
            recipient_list=recipients,
            fail_silently=False,
        )
        logger.info("Email envoyé à %s pour alerte %s", recipients, alert.id)
        return {"status": "success", "recipients": recipients}
    except Exception as exc:
        logger.error("Échec envoi email: %s", exc)
        return {"status": "failed", "error": str(exc)}
