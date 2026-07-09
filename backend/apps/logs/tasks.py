"""
Tâches Celery pour la gestion du cycle de vie des logs.
"""
import logging
from datetime import timedelta

from celery import shared_task
from django.conf import settings
from django.utils import timezone

logger = logging.getLogger(__name__)


@shared_task(name="apps.logs.tasks.cleanup_old_raw_logs")
def cleanup_old_raw_logs():
    """
    Supprime les RawLog plus vieux que LOG_RETENTION_DAYS (défaut 90 jours).
    Les NormalizedLog associés sont supprimés en cascade (OneToOneField).
    Exécutée chaque nuit à 03h00 UTC par Celery Beat.
    """
    from apps.logs.models import RawLog

    retention_days = settings.LOG_RETENTION_DAYS
    threshold = timezone.now() - timedelta(days=retention_days)
    qs = RawLog.objects.filter(received_at__lt=threshold)
    count = qs.count()
    if count > 0:
        qs.delete()
        logger.info(
            "Nettoyage logs bruts : %d RawLog supprimés (> %d jours).",
            count,
            retention_days,
        )
    else:
        logger.info("Nettoyage logs bruts : aucun RawLog à supprimer.")
    return {"deleted_count": count}
