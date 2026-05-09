"""
Règle de détection Brute Force.
Déclencheur : 5 login_failure ou plus du même user_email dans 5 minutes.
MITRE : T1110 - Brute Force / Credential Access
"""
import logging
from datetime import timedelta
from typing import List

from django.db.models import Count, QuerySet
from django.utils import timezone

from .base_rule import BaseRule, RuleMatch

logger = logging.getLogger(__name__)


class BruteForceRule(BaseRule):
    """
    Détecte les tentatives de brute force sur les comptes utilisateurs.
    Analyse les login_failure groupés par user_email dans une fenêtre glissante.
    """

    def evaluate(self, logs: QuerySet, condition: dict) -> List[RuleMatch]:
        """
        Recherche les utilisateurs ayant subi N echecs de connexion
        dans une fenêtre de X secondes.
        """
        threshold_count = condition.get("count", 5)
        window_seconds = condition.get("window_seconds", 300)
        action_filter = condition.get("action", "login_failure")
        field = condition.get("field", "user_email")

        window_start = timezone.now() - timedelta(seconds=window_seconds)

        failure_logs = logs.filter(
            action=action_filter,
            event_time__gte=window_start,
            user_email__isnull=False,
        )

        # Grouper par user_email et compter
        user_counts = (
            failure_logs
            .values("user_email")
            .annotate(failure_count=Count("id"))
            .filter(failure_count__gte=threshold_count)
        )

        matches = []
        for user_stat in user_counts:
            user_email = user_stat["user_email"]
            count = user_stat["failure_count"]

            # Récupérer les logs correspondants pour ce user
            user_logs = list(
                failure_logs.filter(user_email=user_email)
                .order_by("-event_time")[:50]
            )

            match = RuleMatch(
                matched_logs=user_logs,
                context={
                    "user_email": user_email,
                    "failure_count": count,
                    "window_seconds": window_seconds,
                    "threshold": threshold_count,
                },
            )
            matches.append(match)
            logger.info(
                "Brute force détecté : %s — %d tentatives en %ds",
                user_email,
                count,
                window_seconds,
            )

        return matches
