"""
Règle de détection Impossible Travel.
Déclencheur : login_success du même user depuis 2 pays différents en < 2 heures.
MITRE : T1078 - Valid Accounts / Initial Access
"""
import logging
from collections import defaultdict
from datetime import timedelta
from typing import List

from django.utils import timezone

from .base_rule import BaseRule, RuleMatch

logger = logging.getLogger(__name__)


class ImpossibleTravelRule(BaseRule):
    """
    Détecte les connexions géographiquement impossibles.
    Un utilisateur ne peut pas être dans deux pays différents séparés par < 2h.
    """

    def evaluate(self, logs, condition: dict) -> List[RuleMatch]:
        window_seconds = condition.get("window_seconds", 7200)
        window_start = timezone.now() - timedelta(seconds=window_seconds)

        # Filtrer les login_success avec geo_country renseigné
        login_logs = list(
            logs.filter(
                action="login_success",
                event_time__gte=window_start,
                user_email__isnull=False,
                geo_country__isnull=False,
            ).order_by("user_email", "event_time")
        )

        # Grouper par user_email
        by_user = defaultdict(list)
        for log in login_logs:
            by_user[log.user_email].append(log)

        matches = []
        for user_email, user_logs in by_user.items():
            if len(user_logs) < 2:
                continue

            # Une alerte par PAIRE DE PAYS distincte (pas juste la première
            # trouvée) : un utilisateur qui enchaîne FR→US→DE déclenche 2
            # paires différentes (FR/US, US/DE), donc 2 alertes. On dédup
            # seulement les paires identiques (ex: repasser deux fois par le
            # même couple de pays ne recrée pas un doublon dans ce cycle —
            # `_create_alert_if_new` gère la dédup inter-cycles).
            seen_pairs = set()
            for i in range(len(user_logs)):
                for j in range(i + 1, len(user_logs)):
                    log_a = user_logs[i]
                    log_b = user_logs[j]

                    if log_a.geo_country == log_b.geo_country:
                        continue

                    # Calculer le délai entre les deux connexions
                    time_diff = abs((log_b.event_time - log_a.event_time).total_seconds())
                    if time_diff > window_seconds:
                        continue

                    pair_key = frozenset((log_a.geo_country, log_b.geo_country))
                    if pair_key in seen_pairs:
                        continue
                    seen_pairs.add(pair_key)

                    match = RuleMatch(
                        matched_logs=[log_a, log_b],
                        context={
                            "user_email": user_email,
                            "country_1": log_a.geo_country,
                            "country_2": log_b.geo_country,
                            "city_1": log_a.geo_city,
                            "city_2": log_b.geo_city,
                            "time_diff_seconds": round(time_diff),
                            "window_seconds": window_seconds,
                        },
                    )
                    matches.append(match)
                    logger.info(
                        "Impossible travel : %s — %s↔%s en %ds",
                        user_email,
                        log_a.geo_country,
                        log_b.geo_country,
                        time_diff,
                    )

        return matches
