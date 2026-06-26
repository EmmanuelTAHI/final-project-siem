"""
Règle de détection basée sur le niveau d'alerte Wazuh.
Déclencheur : wazuh_level >= threshold OU wazuh_rule_id dans une liste de règles critiques.
MITRE : Variable selon la règle Wazuh déclenchée.
"""
import logging
from typing import List

from django.db.models import QuerySet

from .base_rule import BaseRule, RuleMatch

logger = logging.getLogger(__name__)


class WazuhAlertRule(BaseRule):
    """
    Détecte les événements critiques remontés par l'agent Wazuh.
    Analyse le champ extra_fields.wazuh_level et/ou extra_fields.wazuh_rule_id.
    """

    def evaluate(self, logs: QuerySet, condition: dict) -> List[RuleMatch]:
        min_level = condition.get("min_wazuh_level", 10)
        rule_ids = condition.get("wazuh_rule_ids", [])
        action_filter = condition.get("action")
        group_by_ip = condition.get("group_by_ip", False)

        candidates = logs.filter(source_type="wazuh")
        if action_filter:
            candidates = candidates.filter(action=action_filter)

        matches = []
        seen_contexts = set()

        for log in candidates.select_related():
            extra = log.extra_fields or {}
            wazuh_level = extra.get("wazuh_level", 0)
            wazuh_rule_id = str(extra.get("wazuh_rule_id", ""))

            level_match = wazuh_level >= min_level
            rule_id_match = wazuh_rule_id in [str(r) for r in rule_ids] if rule_ids else False

            if not (level_match or rule_id_match):
                continue

            dedup_key = (log.source_ip or "", log.action or "", wazuh_rule_id)
            if dedup_key in seen_contexts:
                continue
            seen_contexts.add(dedup_key)

            context = {
                "source_ip": log.source_ip or "unknown",
                "user_email": log.user_email or "unknown",
                "action": log.action or "unknown",
                "wazuh_level": wazuh_level,
                "wazuh_rule_id": wazuh_rule_id,
                "hostname": extra.get("hostname", "unknown"),
                "wazuh_rule_description": extra.get("wazuh_rule_description", ""),
            }

            matches.append(RuleMatch(matched_logs=[log], context=context))
            logger.info(
                "Alerte Wazuh : level=%d rule_id=%s ip=%s action=%s",
                wazuh_level,
                wazuh_rule_id,
                log.source_ip,
                log.action,
            )

        return matches
