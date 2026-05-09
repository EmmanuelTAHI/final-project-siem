"""
Règle de détection de contournement MFA.
Déclencheur : login_success avec mfa_detail.authMethod == null
              ou authStepResultDetail == "MFA bypassed"
Sévérité : CRITICAL
"""
import logging
from typing import List

from .base_rule import BaseRule, RuleMatch

logger = logging.getLogger(__name__)


class MFABypassRule(BaseRule):
    """
    Détecte les connexions réussies sans authentification MFA.
    Analyse les extra_fields pour identifier les bypass MFA.
    """

    MFA_BYPASS_INDICATORS = {
        "MFA bypassed",
        "MFA skipped",
        "MfaSkipped",
        "MFABypass",
    }

    def evaluate(self, logs, condition: dict) -> List[RuleMatch]:
        # Filtrer les login_success
        success_logs = logs.filter(
            action="login_success",
            user_email__isnull=False,
        )

        matches = []
        for log in success_logs:
            extra = log.extra_fields or {}
            mfa_detail = extra.get("mfa_detail") or {}
            auth_method = mfa_detail.get("authMethod")
            auth_step_result = mfa_detail.get("authStepResultDetail", "")

            # Cas 1 : authMethod est None (pas de MFA utilisé)
            mfa_absent = mfa_detail and auth_method is None

            # Cas 2 : MFA explicitement bypassé
            mfa_bypassed = any(
                indicator in str(auth_step_result)
                for indicator in self.MFA_BYPASS_INDICATORS
            )

            # Cas 3 : conditional_access_status indique MFA bypass
            conditional_access = extra.get("conditional_access_status", "")
            ca_bypass = str(conditional_access).lower() in ("notapplied", "notEnabled")

            if mfa_absent or mfa_bypassed or ca_bypass:
                match = RuleMatch(
                    matched_logs=[log],
                    context={
                        "user_email": log.user_email,
                        "source_ip": log.source_ip,
                        "event_time": log.event_time.isoformat(),
                        "mfa_detail": mfa_detail,
                        "conditional_access_status": conditional_access,
                        "bypass_reason": (
                            "authMethod=null" if mfa_absent
                            else "MFA explicitement bypassé" if mfa_bypassed
                            else "Conditional Access non appliqué"
                        ),
                    },
                )
                matches.append(match)
                logger.critical(
                    "MFA Bypass détecté : %s — IP=%s",
                    log.user_email,
                    log.source_ip,
                )

        return matches
