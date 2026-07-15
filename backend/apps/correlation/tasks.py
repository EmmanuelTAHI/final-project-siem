"""
Tâches Celery pour le moteur de corrélation.
"""
import logging

from celery import shared_task
from django.core.cache import cache

logger = logging.getLogger(__name__)

LAST_RUN_CACHE_KEY = "correlation_engine_last_run"


@shared_task(name="apps.correlation.tasks.run_correlation_engine", bind=True, max_retries=2)
def run_correlation_engine(self):
    """
    Exécute le moteur de corrélation sur les nouveaux logs.
    Stocke l'horodatage de la dernière exécution dans Redis.
    Planifié toutes les 20 secondes par Celery Beat.
    """
    from apps.correlation.engine import correlation_engine
    from django.utils import timezone

    last_run_str = cache.get(LAST_RUN_CACHE_KEY)
    last_run_at = None
    if last_run_str:
        from datetime import datetime
        last_run_at = datetime.fromisoformat(last_run_str)

    try:
        result = correlation_engine.run(last_run_at=last_run_at)
        cache.set(LAST_RUN_CACHE_KEY, timezone.now().isoformat(), timeout=3600)
        logger.info("Corrélation terminée : %s", result)
        return result
    except Exception as exc:
        logger.exception("Erreur lors de l'exécution du moteur de corrélation : %s", exc)
        raise self.retry(exc=exc, countdown=60)
