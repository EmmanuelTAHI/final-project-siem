"""
Règle de détection d'exfiltration de données.
Déclencheur : volume anormalement élevé de données transférées vers l'extérieur
OU actions d'exfiltration connues (archive, upload, dns_exfil).
MITRE : T1048 - Exfiltration Over Alternative Protocol
"""
import logging
from datetime import timedelta
from typing import List

from django.db.models import QuerySet
from django.utils import timezone

from .base_rule import BaseRule, RuleMatch

logger = logging.getLogger(__name__)


class DataExfilRule(BaseRule):
    """
    Détecte les tentatives d'exfiltration de données.
    Combine analyse volumétrique et détection d'actions suspectes.
    """

    def evaluate(self, logs: QuerySet, condition: dict) -> List[RuleMatch]:
        min_events = condition.get("min_events", 10)
        window_seconds = condition.get("window_seconds", 600)
        exfil_actions = condition.get("actions", [
            "data_exfil", "dns_exfil", "file_upload", "large_transfer",
            "email_forward", "archive_created", "usb_write",
        ])

        window_start = timezone.now() - timedelta(seconds=window_seconds)

        candidate_logs = logs.filter(
            action__in=exfil_actions,
            event_time__gte=window_start,
            source_ip__isnull=False,
        )

        from collections import defaultdict
        by_source: dict = defaultdict(list)
        for log in candidate_logs:
            by_source[log.source_ip].append(log)

        matches = []
        for source_ip, src_logs in by_source.items():
            if len(src_logs) < min_events:
                continue

            actions_seen = list(set(l.action for l in src_logs if l.action))
            destinations = list(set(l.destination_ip for l in src_logs if l.destination_ip))

            context = {
                "source_ip": source_ip,
                "event_count": len(src_logs),
                "distinct_destinations": len(destinations),
                "actions_observed": ", ".join(actions_seen[:5]),
                "window_seconds": window_seconds,
                "user_email": next((l.user_email for l in src_logs if l.user_email), "unknown"),
            }

            matches.append(RuleMatch(matched_logs=src_logs[:50], context=context))
            logger.info(
                "Exfiltration détectée : %s — %d événements en %ds",
                source_ip,
                len(src_logs),
                window_seconds,
            )

        return matches
