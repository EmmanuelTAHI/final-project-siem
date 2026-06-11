"""
Tâches Celery pour la collecte planifiée des logs.
Déclenchées par Celery Beat selon le planning défini dans config/celery.py.
"""
import logging

from celery import shared_task

from apps.collectors.models import ConnectorConfig

logger = logging.getLogger(__name__)


def _collect_for_connector(connector: ConnectorConfig):
    """Exécute la collecte pour un connecteur donné et normalise les logs."""
    from apps.collectors.sources.microsoft_collector import MicrosoftCollector
    from apps.collectors.sources.google_collector import GoogleCollector
    from apps.collectors.sources.wazuh_collector import WazuhCollector
    from apps.collectors.sources.syslog_collector import SyslogCollector

    collector_map = {
        "microsoft365": MicrosoftCollector,
        "google_workspace": GoogleCollector,
        "wazuh": WazuhCollector,
        "syslog": SyslogCollector,  # push-based : normalize_all() uniquement
    }
    collector_class = collector_map.get(connector.source_type)
    if not collector_class:
        logger.warning("Aucun collecteur pour le type : %s", connector.source_type)
        return

    try:
        collector = collector_class(connector)
        job = collector.collect()
        # Normaliser les logs bruts collectés
        normalized_count = collector.normalize_all()
        logger.info(
            "Collecte %s : %d logs bruts, %d normalisés (job=%s, statut=%s)",
            connector.name,
            job.logs_collected_count,
            normalized_count,
            job.id,
            job.status,
        )
    except Exception as exc:
        logger.exception(
            "Erreur collecte %s (%s) : %s",
            connector.name,
            connector.source_type,
            str(exc),
        )


@shared_task(name="apps.collectors.tasks.collect_all_microsoft_connectors", bind=True, max_retries=3)
def collect_all_microsoft_connectors(self):
    """Collecte les logs depuis tous les connecteurs Microsoft 365 actifs."""
    connectors = ConnectorConfig.objects.filter(
        source_type="microsoft365",
        is_active=True,
        oauth_access_token__isnull=False,
    )
    logger.info("Lancement collecte Microsoft 365 : %d connecteur(s)", connectors.count())
    for connector in connectors:
        try:
            _collect_for_connector(connector)
        except Exception as exc:
            logger.error("Collecte Microsoft %s échouée : %s", connector.name, exc)


@shared_task(name="apps.collectors.tasks.collect_all_google_connectors", bind=True, max_retries=3)
def collect_all_google_connectors(self):
    """Collecte les logs depuis tous les connecteurs Google Workspace actifs."""
    connectors = ConnectorConfig.objects.filter(
        source_type="google_workspace",
        is_active=True,
        oauth_access_token__isnull=False,
    )
    logger.info("Lancement collecte Google Workspace : %d connecteur(s)", connectors.count())
    for connector in connectors:
        try:
            _collect_for_connector(connector)
        except Exception as exc:
            logger.error("Collecte Google %s échouée : %s", connector.name, exc)


@shared_task(name="apps.collectors.tasks.collect_all_wazuh_connectors", bind=True, max_retries=3)
def collect_all_wazuh_connectors(self):
    """Collecte les alertes depuis tous les connecteurs Wazuh actifs."""
    connectors = ConnectorConfig.objects.filter(
        source_type="wazuh",
        is_active=True,
    )
    logger.info("Lancement collecte Wazuh : %d connecteur(s)", connectors.count())
    for connector in connectors:
        try:
            _collect_for_connector(connector)
        except Exception as exc:
            logger.error("Collecte Wazuh %s échouée : %s", connector.name, exc)


@shared_task(name="apps.collectors.tasks.refresh_expiring_tokens", bind=True, max_retries=2)
def refresh_expiring_tokens(self):
    """
    Rafraîchit les tokens OAuth2 qui vont expirer dans moins de 5 minutes.
    Exécuté toutes les heures par Celery Beat.
    """
    import django.utils.timezone as timezone
    from datetime import timedelta
    from apps.authentication.services.token_service import token_service

    threshold = timezone.now() + timedelta(minutes=5)
    connectors = ConnectorConfig.objects.filter(
        is_active=True,
        oauth_refresh_token__isnull=False,
        token_expires_at__lte=threshold,
    )
    logger.info("Refresh tokens expirés : %d connecteur(s) concerné(s)", connectors.count())
    for connector in connectors:
        try:
            token_service.refresh_token(connector)
            logger.info("Token rafraîchi pour %s.", connector.name)
        except Exception as exc:
            logger.error(
                "Erreur refresh token pour %s : %s",
                connector.name,
                str(exc),
            )


@shared_task(name="apps.collectors.tasks.collect_all_syslog_connectors", bind=True, max_retries=1)
def collect_all_syslog_connectors(self):
    """
    Syslog est push-based : les logs arrivent via receive_syslog et sont déjà en RawLog.
    Cette tâche normalise tous les RawLog syslog en attente.
    Planifiée toutes les 2 minutes par Celery Beat.
    """
    connectors = ConnectorConfig.objects.filter(source_type="syslog", is_active=True)
    logger.info("Normalisation syslog : %d connecteur(s) actif(s)", connectors.count())
    for connector in connectors:
        try:
            from apps.collectors.sources.syslog_collector import SyslogCollector
            count = SyslogCollector(connector).normalize_all()
            logger.info("Syslog normalize %s : %d logs.", connector.name, count)
        except Exception as exc:
            logger.error("Erreur normalize syslog %s : %s", connector.name, exc)


@shared_task(name="apps.collectors.tasks.normalize_syslog_raw_logs", bind=True, max_retries=2)
def normalize_syslog_raw_logs(self, connector_id: str):
    """
    Normalise les RawLog syslog en attente pour un connecteur donné.
    Déclenché à la volée par receive_syslog après chaque batch de N logs.
    """
    try:
        connector = ConnectorConfig.objects.get(id=connector_id, is_active=True)
        from apps.collectors.sources.syslog_collector import SyslogCollector
        count = SyslogCollector(connector).normalize_all()
        logger.info("Syslog : %d logs normalisés pour %s.", count, connector.name)
        return {"normalized": count}
    except ConnectorConfig.DoesNotExist:
        logger.error("Connecteur syslog introuvable ou inactif : %s", connector_id)
        return {"normalized": 0}
    except Exception as exc:
        logger.exception("Erreur normalisation syslog %s : %s", connector_id, exc)
        raise self.retry(exc=exc, countdown=30)


@shared_task(name="apps.collectors.tasks.manual_collect", bind=True, max_retries=1)
def manual_collect(self, connector_id: str):
    """
    Déclenche une collecte manuelle pour un connecteur spécifique.
    Appelé depuis l'endpoint POST /api/collectors/connectors/{id}/collect/
    """
    try:
        connector = ConnectorConfig.objects.get(id=connector_id, is_active=True)
        _collect_for_connector(connector)
        return {"status": "success", "connector": connector.name}
    except ConnectorConfig.DoesNotExist:
        logger.error("Connecteur introuvable ou inactif : %s", connector_id)
        return {"status": "error", "message": "Connecteur introuvable."}
    except Exception as exc:
        logger.exception("Erreur collecte manuelle pour %s : %s", connector_id, exc)
        raise self.retry(exc=exc, countdown=30)
