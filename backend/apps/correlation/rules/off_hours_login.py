"""
Règle de détection Off-Hours Login.
Déclencheur : login_success entre 20h00 et 07h00 UTC.
Sévérité : MEDIUM
"""
import logging
from typing import List

from .base_rule import BaseRule, RuleMatch

logger = logging.getLogger(__name__)


class OffHoursLoginRule(BaseRule):
    """
    Détecte les connexions effectuées en dehors des heures ouvrables.
    Horaires considérés hors-bureau : 20h00 à 07h00 UTC.
    """

    def evaluate(self, logs, condition: dict) -> List[RuleMatch]:
        action_filter = condition.get("action", "login_success")
        forbidden_start = condition.get("forbidden_hours_start", 20)
        forbidden_end = condition.get("forbidden_hours_end", 7)

        # Filtrer les login_success dans les nouveaux logs
        login_logs = logs.filter(
            action=action_filter,
            user_email__isnull=False,
        )

        matches = []
        for log in login_logs:
            hour = log.event_time.hour

            # Heure hors-bureau : après 20h OU avant 7h
            if hour >= forbidden_start or hour < forbidden_end:
                match = RuleMatch(
                    matched_logs=[log],
                    context={
                        "user_email": log.user_email,
                        "hour_utc": hour,
                        "event_time": log.event_time.isoformat(),
                        "forbidden_start": forbidden_start,
                        "forbidden_end": forbidden_end,
                        "source_ip": log.source_ip,
                        "geo_country": log.geo_country,
                    },
                )
                matches.append(match)
                logger.info(
                    "Off-hours login : %s à %dh UTC (%s)",
                    log.user_email,
                    hour,
                    log.event_time.isoformat(),
                )

        return matches
