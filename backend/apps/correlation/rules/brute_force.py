"""
Règle de détection Brute Force.

Deux angles de détection combinés, car un attaquant peut contourner l'un ou
l'autre :
1. Par COMPTE CIBLÉ : N échecs sur le même user_email en fenêtre glissante
   (credential stuffing — un compte attaqué depuis plusieurs IP).
2. Par IP SOURCE : N échecs depuis la même IP, quel que soit le compte ciblé
   (password spraying / brute force qui fait tourner les noms d'utilisateur
   pour éviter qu'un seul compte n'atteigne le seuil — sinon totalement
   invisible pour une règle qui ne regarderait que le compte ciblé).

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
    Détecte les tentatives de brute force, groupées par compte ciblé ET par
    IP source — un attaquant qui fait tourner les noms d'utilisateur pour
    rester sous le seuil "par compte" reste détecté par le seuil "par IP".
    """

    def evaluate(self, logs: QuerySet, condition: dict) -> List[RuleMatch]:
        threshold_count = condition.get("count", 5)
        window_seconds = condition.get("window_seconds", 300)
        action_filter = condition.get("action", "login_failure")

        window_start = timezone.now() - timedelta(seconds=window_seconds)
        failure_logs = logs.filter(action=action_filter, event_time__gte=window_start)

        matches = self._match_by_user(failure_logs, threshold_count, window_seconds)
        matches += self._match_by_source_ip(failure_logs, threshold_count, window_seconds)
        return matches

    def _match_by_user(self, failure_logs: QuerySet, threshold_count: int, window_seconds: int) -> List[RuleMatch]:
        """Angle 1 : N échecs sur le même compte, indépendamment de l'IP source."""
        user_counts = (
            failure_logs
            .filter(user_email__isnull=False)
            .values("user_email")
            .annotate(failure_count=Count("id"))
            .filter(failure_count__gte=threshold_count)
        )

        matches = []
        for user_stat in user_counts:
            user_email = user_stat["user_email"]
            count = user_stat["failure_count"]
            user_logs = list(
                failure_logs.filter(user_email=user_email).order_by("-event_time")[:50]
            )
            matches.append(RuleMatch(
                matched_logs=user_logs,
                context={
                    "user_email": user_email,
                    "failure_count": count,
                    "window_seconds": window_seconds,
                    "threshold": threshold_count,
                    "detection_angle": "user",
                },
            ))
            logger.info(
                "Brute force détecté (par compte) : %s — %d tentatives en %ds",
                user_email, count, window_seconds,
            )
        return matches

    def _match_by_source_ip(self, failure_logs: QuerySet, threshold_count: int, window_seconds: int) -> List[RuleMatch]:
        """
        Angle 2 : N échecs depuis la même IP, tous comptes confondus — détecte
        un brute force qui fait volontairement tourner les noms d'utilisateur
        pour qu'aucun compte individuel n'atteigne jamais le seuil "par compte".
        """
        ip_counts = (
            failure_logs
            .filter(source_ip__isnull=False)
            .values("source_ip")
            .annotate(failure_count=Count("id"))
            .filter(failure_count__gte=threshold_count)
        )

        matches = []
        for ip_stat in ip_counts:
            source_ip = ip_stat["source_ip"]
            count = ip_stat["failure_count"]
            ip_logs_qs = failure_logs.filter(source_ip=source_ip)
            ip_logs = list(ip_logs_qs.order_by("-event_time")[:50])

            distinct_users = list(
                ip_logs_qs.exclude(user_email__isnull=True)
                .values_list("user_email", flat=True)
                .distinct()[:10]
            )

            # Évite un doublon fonctionnel avec l'angle "par compte" : si un
            # seul compte est ciblé depuis cette IP, l'angle 1 l'a déjà couvert
            # (ou le couvrira dès qu'il atteint son propre seuil) — l'angle IP
            # n'apporte de valeur QUE quand plusieurs comptes sont dispersés.
            if len(distinct_users) <= 1:
                continue

            matches.append(RuleMatch(
                matched_logs=ip_logs,
                context={
                    # Le template d'alerte par défaut utilise {user_email} —
                    # une valeur descriptive évite un KeyError et reste lisible.
                    "user_email": f"{len(distinct_users)} comptes différents",
                    "source_ip": source_ip,
                    "distinct_usernames": ", ".join(distinct_users),
                    "failure_count": count,
                    "window_seconds": window_seconds,
                    "threshold": threshold_count,
                    "detection_angle": "source_ip",
                },
            ))
            logger.info(
                "Brute force détecté (par IP) : %s — %d tentatives en %ds sur %d comptes (%s)",
                source_ip, count, window_seconds, len(distinct_users), ", ".join(distinct_users),
            )
        return matches
