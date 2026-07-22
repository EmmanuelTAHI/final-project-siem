"""
Règle de détection Résultats de scan de sécurité (rkhunter/ClamAV).
Déclencheur : un NormalizedLog issu du scan quotidien rkhunter (rootkits) ou
ClamAV (malware), ingéré via le pipeline syslog existant (facility local5,
voir normalizer.py::_map_security_scan). Une seule correspondance suffit par
log, pas de seuil — chaque détection est notable en soi.
MITRE : T1543 (rkhunter, persistance/modification système détectée) /
T1204/T1105 (ClamAV, présence de malware).
"""
import logging
from typing import List

from django.db.models import QuerySet

from .base_rule import BaseRule, RuleMatch

logger = logging.getLogger(__name__)


class SecurityScanFindingRule(BaseRule):
    """
    Détecte les résultats de scan de sécurité (rkhunter, ClamAV). Le type
    d'action à surveiller est fourni par condition_logic["actions"], ce qui
    permet de définir une règle séparée (et donc une sévérité séparée) par
    outil : malware_detected (critique) vs rootkit_scan_finding (moyen).
    """

    def evaluate(self, logs: QuerySet, condition: dict) -> List[RuleMatch]:
        actions = condition.get("actions", ["malware_detected", "rootkit_scan_finding"])
        matches = []
        for log in logs.filter(action__in=actions):
            extra = log.extra_fields or {}
            matches.append(RuleMatch(
                matched_logs=[log],
                context={
                    "tool": extra.get("scan_tool", "?"),
                    "hostname": extra.get("hostname", "?"),
                    "finding": (log.resource or "")[:300],
                },
            ))
            logger.info(
                "Résultat de scan de sécurité détecté : %s — %s (%s)",
                extra.get("scan_tool", "?"), log.resource, log.action,
            )
        return matches
