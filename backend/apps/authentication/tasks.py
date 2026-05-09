"""
Tâches Celery pour la surveillance des comptes liés.
Planifiées par Celery Beat (cf. config/celery.py ou settings.CELERY_BEAT_SCHEDULE).
"""
import logging

from celery import shared_task

logger = logging.getLogger(__name__)


@shared_task(
    name="apps.authentication.tasks.poll_linked_accounts",
    bind=True,
    max_retries=2,
)
def poll_linked_accounts(self):
    """Poll tous les LinkedAccount actifs (Google / Microsoft / GitHub)."""
    from .services.personal_security_service import poll_all_active_accounts

    try:
        result = poll_all_active_accounts()
        logger.info("poll_linked_accounts: %s", result)
        return result
    except Exception as exc:
        logger.exception("poll_linked_accounts failed")
        raise self.retry(exc=exc, countdown=60)


@shared_task(name="apps.authentication.tasks.expire_login_confirmations")
def expire_login_confirmations():
    """Marque les LoginConfirmation pending expirées comme `expired`."""
    from django.utils import timezone

    from .models import LoginConfirmation

    n = LoginConfirmation.objects.filter(
        status="pending", expires_at__lte=timezone.now()
    ).update(status="expired")
    logger.info("expire_login_confirmations: %d", n)
    return {"expired": n}
