"""
Tâches Celery pour la gestion du cycle de vie des logs.
"""
import logging
from datetime import timedelta

from celery import shared_task
from django.utils import timezone

logger = logging.getLogger(__name__)


@shared_task(name="apps.logs.tasks.cleanup_old_raw_logs")
def cleanup_old_raw_logs():
    """
    Supprime les RawLog de plus de 90 jours.
    Exécutée chaque nuit à 03h00 UTC par Celery Beat.
    """
    from apps.logs.models import RawLog

    threshold = timezone.now() - timedelta(days=90)
    qs = RawLog.objects.filter(received_at__lt=threshold)
    count = qs.count()
    if count > 0:
        qs.delete()
        logger.info("Nettoyage logs bruts : %d RawLog supprimés (>90 jours).", count)
    else:
        logger.info("Nettoyage logs bruts : aucun RawLog à supprimer.")
    return {"deleted_count": count}
