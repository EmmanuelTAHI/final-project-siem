"""
Règle de détection de balises C2 (Command & Control Beaconing).
Déclencheur : connexions sortantes régulières depuis une même IP vers une même cible
avec un intervalle quasi-constant (jitter < threshold).
MITRE : T1071 - Application Layer Protocol / Command and Control
"""
import logging
from datetime import timedelta
from typing import List

from django.db.models import QuerySet
from django.utils import timezone

from .base_rule import BaseRule, RuleMatch

logger = logging.getLogger(__name__)


class C2BeaconRule(BaseRule):
    """
    Détecte les comportements de beaconing C2.
    Analyse la régularité des connexions sortantes (faible variance inter-événements).
    """

    def evaluate(self, logs: QuerySet, condition: dict) -> List[RuleMatch]:
        min_beacons = condition.get("min_beacons", 5)
        window_seconds = condition.get("window_seconds", 3600)
        actions = condition.get("actions", ["dns_query", "http_request", "https_request", "outbound_connection", "c2_beacon"])
        max_jitter_ratio = condition.get("max_jitter_ratio", 0.3)

        window_start = timezone.now() - timedelta(seconds=window_seconds)

        candidate_logs = logs.filter(
            action__in=actions,
            event_time__gte=window_start,
            source_ip__isnull=False,
        )

        from collections import defaultdict
        by_pair: dict = defaultdict(list)
        for log in candidate_logs:
            key = (log.source_ip, log.destination_ip or log.resource or "")
            by_pair[key].append(log)

        matches = []
        for (src_ip, dst), pair_logs in by_pair.items():
            if len(pair_logs) < min_beacons:
                continue

            pair_logs_sorted = sorted(pair_logs, key=lambda l: l.event_time)
            timestamps = [l.event_time.timestamp() for l in pair_logs_sorted]

            if len(timestamps) < 2:
                continue

            intervals = [timestamps[i+1] - timestamps[i] for i in range(len(timestamps)-1)]
            avg_interval = sum(intervals) / len(intervals)

            if avg_interval == 0:
                continue

            deviations = [abs(iv - avg_interval) for iv in intervals]
            jitter_ratio = (sum(deviations) / len(deviations)) / avg_interval

            if jitter_ratio > max_jitter_ratio:
                continue

            context = {
                "source_ip": src_ip,
                "destination": dst or "unknown",
                "beacon_count": len(pair_logs),
                "avg_interval_seconds": round(avg_interval, 1),
                "jitter_ratio": round(jitter_ratio, 3),
                "window_seconds": window_seconds,
                "action": pair_logs[0].action if pair_logs else "unknown",
                "user_email": next((l.user_email for l in pair_logs if l.user_email), "unknown"),
            }

            matches.append(RuleMatch(matched_logs=pair_logs[:50], context=context))
            logger.info(
                "Beacon C2 détecté : %s -> %s — %d connexions, intervalle=%.1fs, jitter=%.1f%%",
                src_ip,
                dst,
                len(pair_logs),
                avg_interval,
                jitter_ratio * 100,
            )

        return matches
