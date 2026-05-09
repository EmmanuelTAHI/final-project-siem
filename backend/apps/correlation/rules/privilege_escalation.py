"""
Règle de détection d'escalade de privilèges.
Déclencheur : action contenant privilege_change ou role_assigned avec rôle admin.
MITRE : T1078.003 - Local Accounts / Privilege Escalation
"""
import logging
from typing import List

from .base_rule import BaseRule, RuleMatch

logger = logging.getLogger(__name__)


class PrivilegeEscalationRule(BaseRule):
    """
    Détecte les élévations de privilèges vers des rôles administrateur.
    Surveille les actions privilege_change et role_assigned.
    """

    PRIVILEGE_ACTIONS = {
        "privilege_change",
        "role_assigned",
        "admin_role_assigned",
        "roleAssignment",
        "Add member to role",
    }

    ADMIN_KEYWORDS = {"admin", "administrator", "global", "superuser", "root", "privileged"}

    def evaluate(self, logs, condition: dict) -> List[RuleMatch]:
        # Filtrer les logs susceptibles d'être des escalades
        candidate_logs = logs.filter(
            user_email__isnull=False,
        )

        matches = []
        for log in candidate_logs:
            action_lower = log.action.lower()

            # Vérifier si l'action est liée à une élévation de privilèges
            is_privilege_action = any(
                priv_action.lower() in action_lower
                for priv_action in self.PRIVILEGE_ACTIONS
            )

            if not is_privilege_action:
                continue

            # Vérifier si le nouveau rôle contient "admin" dans les extra_fields
            extra = log.extra_fields or {}
            new_role = (
                extra.get("new_role", "")
                or extra.get("role", "")
                or extra.get("roleName", "")
                or extra.get("targetRole", "")
                or ""
            ).lower()

            is_admin_role = any(kw in new_role for kw in self.ADMIN_KEYWORDS) if new_role else True

            if is_admin_role:
                match = RuleMatch(
                    matched_logs=[log],
                    context={
                        "user_email": log.user_email,
                        "action": log.action,
                        "new_role": new_role or "inconnu",
                        "source_ip": log.source_ip,
                        "event_time": log.event_time.isoformat(),
                        "extra_fields": extra,
                    },
                )
                matches.append(match)
                logger.warning(
                    "Privilege escalation : %s — action=%s — rôle=%s",
                    log.user_email,
                    log.action,
                    new_role or "inconnu",
                )

        return matches
