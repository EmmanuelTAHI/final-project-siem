"""
Classe abstraite BaseCollector.
Tous les collecteurs de sources de logs héritent de cette classe.
"""
import logging
from abc import ABC, abstractmethod
from typing import Generator

import django.utils.timezone as timezone

from apps.collectors.models import CollectionJob, ConnectorConfig
from apps.logs.models import RawLog

logger = logging.getLogger(__name__)


class BaseCollector(ABC):
    """
    Classe abstraite définissant l'interface commune à tous les collecteurs.
    Gère le cycle de vie d'un job de collecte et le stockage des logs bruts.
    """

    def __init__(self, connector: ConnectorConfig):
        self.connector = connector
        self.job: CollectionJob | None = None

    def collect(self) -> CollectionJob:
        """
        Point d'entrée principal de la collecte.
        Crée un job, exécute la collecte, met à jour le connecteur.
        """
        self.job = CollectionJob.objects.create(
            connector=self.connector,
            status="running",
            started_at=timezone.now(),
        )
        logger.info(
            "Démarrage collecte %s pour connecteur %s (job=%s)",
            self.__class__.__name__,
            self.connector.name,
            self.job.id,
        )

        collected_count = 0
        try:
            for raw_data in self.fetch_logs():
                self._store_raw_log(raw_data)
                collected_count += 1

            self.connector.last_collected_at = timezone.now()
            self.connector.save(update_fields=["last_collected_at"])

            self.job.status = "success"
            self.job.logs_collected_count = collected_count
            logger.info(
                "Collecte terminée : %d logs pour %s",
                collected_count,
                self.connector.name,
            )

        except Exception as exc:
            logger.exception(
                "Erreur lors de la collecte pour %s : %s",
                self.connector.name,
                str(exc),
            )
            self.job.status = "failed"
            self.job.error_message = str(exc)

        finally:
            self.job.finished_at = timezone.now()
            self.job.save(
                update_fields=["status", "logs_collected_count", "error_message", "finished_at"]
            )

        return self.job

    @abstractmethod
    def fetch_logs(self) -> Generator[dict, None, None]:
        """
        Générateur qui yield les logs bruts depuis la source.
        Chaque élément est un dict représentant un événement brut.
        Doit implémenter la pagination si nécessaire.
        """
        raise NotImplementedError

    @abstractmethod
    def test_connection(self) -> dict:
        """
        Teste la connexion à la source et retourne :
        {"reachable": bool, "latency_ms": float, "message": str}
        """
        raise NotImplementedError

    def _store_raw_log(self, raw_data: dict) -> RawLog:
        """Stocke un log brut dans la base de données."""
        return RawLog.objects.create(
            source_type=self.connector.source_type,
            connector=self.connector,
            organization=self.connector.organization,
            raw_data=raw_data,
        )

    def normalize_all(self) -> int:
        """
        Normalise tous les RawLog non encore normalisés pour ce connecteur.
        Retourne le nombre de logs normalisés.
        """
        from apps.logs.normalizer import LogNormalizer

        raw_logs = RawLog.objects.filter(
            connector=self.connector,
            is_normalized=False,
        )
        normalizer = LogNormalizer()
        count = 0
        ips_needing_geo: set[str] = set()
        for raw_log in raw_logs:
            try:
                normalized = normalizer.normalize(raw_log)
                count += 1
                if normalized and normalized.source_ip and not normalized.geo_country:
                    ips_needing_geo.add(normalized.source_ip)
            except Exception as exc:
                logger.warning("Impossible de normaliser RawLog %s : %s", raw_log.id, exc)

        if ips_needing_geo:
            self._geo_tag_ips(ips_needing_geo)

        if count > 0:
            self._trigger_correlation_now()

        return count

    @staticmethod
    def _trigger_correlation_now() -> None:
        """
        Déclenche immédiatement une passe du moteur de corrélation dès que de
        nouveaux logs viennent d'être normalisés, au lieu d'attendre le prochain
        tick périodique (Celery Beat) — c'est ce qui rend la détection quasi
        instantanée (ex. scan de test) plutôt que bornée par l'intervalle de
        polling. Le tick périodique reste en place comme filet de sécurité.
        """
        try:
            from apps.correlation.tasks import run_correlation_engine
            run_correlation_engine.delay()
        except Exception as exc:
            logger.warning("Déclenchement immédiat de la corrélation impossible : %s", exc)

    def _geo_tag_ips(self, ips: set[str]) -> None:
        """
        Géolocalise immédiatement les IP nouvellement vues (une requête par IP
        unique, pas par log) pour que "Trafic & IP" affiche les pays même sur
        un lot d'un seul log, sans attendre la tâche périodique d'enrichissement
        CTI (désactivée) qui ne géolocalisait qu'en lot toutes les 15 min.
        """
        from apps.logs.models import NormalizedLog
        from apps.threat_intel.services import ip_enrichment

        for ip in ips:
            try:
                geo = ip_enrichment.geo_lookup(ip)
            except Exception as exc:
                logger.warning("Géolookup impossible pour %s : %s", ip, exc)
                continue
            country_code = geo.get("countryCode")
            if country_code:
                NormalizedLog.objects.filter(
                    source_ip=ip, geo_country__isnull=True
                ).update(geo_country=country_code, geo_city=geo.get("city") or None)
