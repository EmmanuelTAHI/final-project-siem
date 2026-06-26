"""
Règle de détection de mouvement latéral.
Déclencheur : une même IP source se connecte à N+ hôtes distincts dans une fenêtre de temps.
MITRE : T1021 - Remote Services / Lateral Movement
"""
import logging
from datetime import timedelta
from typing import List

from django.db.models import QuerySet
from django.utils import timezone

from .base_rule import BaseRule, RuleMatch

logger = logging.getLogger(__name__)


class LateralMovementRule(BaseRule):
    """
    Détecte les mouvements latéraux par analyse du nombre d'hôtes cibles
    distincts atteints depuis une même IP source dans une fenêtre glissante.
    """

    def evaluate(self, logs: QuerySet, condition: dict) -> List[RuleMatch]:
        min_hosts = condition.get("min_distinct_hosts", 3)
        window_seconds = condition.get("window_seconds", 300)
        actions = condition.get("actions", ["smb_connect", "rdp_connect", "ssh_connect", "network_scan"])

        window_start = timezone.now() - timedelta(seconds=window_seconds)

        candidate_logs = logs.filter(
            action__in=actions,
            event_time__gte=window_start,
            source_ip__isnull=False,
            destination_ip__isnull=False,
        )

        # Grouper par source_ip
        from collections import defaultdict
        by_source: dict = defaultdict(list)
        for log in candidate_logs:
            by_source[log.source_ip].append(log)

        matches = []
        for source_ip, ip_logs in by_source.items():
            distinct_destinations = set(l.destination_ip for l in ip_logs if l.destination_ip)
            if len(distinct_destinations) < min_hosts:
                continue

            context = {
                "source_ip": source_ip,
                "distinct_hosts_count": len(distinct_destinations),
                "target_hosts": ", ".join(list(distinct_destinations)[:10]),
                "window_seconds": window_seconds,
                "actions_observed": ", ".join(set(l.action for l in ip_logs if l.action)),
                "user_email": next((l.user_email for l in ip_logs if l.user_email), "unknown"),
            }

            matches.append(RuleMatch(matched_logs=ip_logs[:50], context=context))
            logger.info(
                "Mouvement latéral détecté : %s -> %d hôtes distincts en %ds",
                source_ip,
                len(distinct_destinations),
                window_seconds,
            )

        return matches
