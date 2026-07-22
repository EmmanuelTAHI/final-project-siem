"""
Règle de détection Scan web (panneaux admin, chemins sensibles).
Déclencheur : N réponses 403/404 sur des chemins DISTINCTS depuis la même IP
dans une fenêtre glissante — le volume de chemins distincts est le signal,
pas une liste de chemins sensibles à maintenir à la main (couvre aussi bien
/wp-admin que /phpmyadmin ou n'importe quel chemin inconnu du site).
MITRE : T1595 - Active Scanning
"""
import logging
from datetime import timedelta
from typing import List

from django.db.models import Count, QuerySet
from django.utils import timezone

from .base_rule import BaseRule, RuleMatch

logger = logging.getLogger(__name__)


class WebScanDetectionRule(BaseRule):
    """Détecte un balayage de chemins (scan de panneaux admin/fichiers sensibles) par IP."""

    def evaluate(self, logs: QuerySet, condition: dict) -> List[RuleMatch]:
        threshold_count = condition.get("count", 10)
        window_seconds = condition.get("window_seconds", 300)

        window_start = timezone.now() - timedelta(seconds=window_seconds)
        scan_logs = logs.filter(
            action="http_request",
            event_time__gte=window_start,
            extra_fields__http_status__in=[403, 404],
        ).exclude(source_ip__isnull=True)

        ip_counts = (
            scan_logs
            .values("source_ip")
            .annotate(distinct_paths=Count("resource", distinct=True))
            .filter(distinct_paths__gte=threshold_count)
        )

        matches = []
        for ip_stat in ip_counts:
            ip = ip_stat["source_ip"]
            ip_logs = list(scan_logs.filter(source_ip=ip).order_by("-event_time")[:50])
            sample_paths = list(dict.fromkeys(log.resource for log in ip_logs if log.resource))[:8]

            matches.append(RuleMatch(
                matched_logs=ip_logs,
                context={
                    "source_ip": ip,
                    "distinct_paths_count": ip_stat["distinct_paths"],
                    "sample_paths": ", ".join(sample_paths),
                    "window_seconds": window_seconds,
                },
            ))
            logger.info(
                "Scan web détecté : %s — %d chemins distincts (403/404) en %ds",
                ip, ip_stat["distinct_paths"], window_seconds,
            )
        return matches
