"""
Règle de détection Signature d'attaque web.
Déclencheur : une requête HTTP dont le chemin (ou le referer) correspond à
un motif connu d'injection SQL, de traversée de répertoires, ou d'injection
de commande/script — une seule correspondance suffit, pas de seuil.
MITRE : T1190 - Exploit Public-Facing Application
"""
import logging
import re
from typing import List

from django.db.models import Q, QuerySet

from .base_rule import BaseRule, RuleMatch

logger = logging.getLogger(__name__)

# Chaque motif est volontairement large (faux positifs occasionnels
# acceptables sur un chemin légitime contenant "select" par exemple) —
# l'objectif est de détecter des tentatives grossières/automatisées, pas de
# remplacer un WAF. Catégorie affichée dans le titre de l'alerte.
_SIGNATURES = {
    "injection_sql": re.compile(
        r"union\s+select|'\s*or\s*'?1'?\s*=\s*'?1|sleep\(\d|benchmark\(|--\s|#\s*$|;\s*drop\s+table",
        re.IGNORECASE,
    ),
    "traversee_repertoires": re.compile(
        r"\.\./|\.\.%2f|%2e%2e|/etc/passwd|/etc/shadow|c:\\windows",
        re.IGNORECASE,
    ),
    "injection_commande_script": re.compile(
        r"<script|;\s*cat\s+|\$\{jndi:|`.*`|\|\s*nc\s+",
        re.IGNORECASE,
    ),
}


class WebAttackSignatureRule(BaseRule):
    """
    Détecte les motifs connus d'attaque web (injection SQL, traversée de
    répertoires, injection de commande) dans le chemin ou le referer d'une
    requête HTTP normalisée (source nginx).
    """

    def evaluate(self, logs: QuerySet, condition: dict) -> List[RuleMatch]:
        http_logs = logs.filter(action="http_request").exclude(resource__isnull=True)

        matches = []
        for log in http_logs:
            haystack = f"{log.resource or ''} {(log.extra_fields or {}).get('http_referer') or ''}"
            for category, pattern in _SIGNATURES.items():
                if pattern.search(haystack):
                    matches.append(RuleMatch(
                        matched_logs=[log],
                        context={
                            "source_ip": log.source_ip,
                            "category": category.replace("_", " "),
                            "path": (log.resource or "")[:200],
                            "http_method": (log.extra_fields or {}).get("http_method", "?"),
                        },
                    ))
                    logger.info(
                        "Signature d'attaque web détectée : %s — %s %s depuis %s",
                        category, (log.extra_fields or {}).get("http_method", "?"),
                        log.resource, log.source_ip,
                    )
                    break  # une catégorie suffit par requête, évite les doublons
        return matches
