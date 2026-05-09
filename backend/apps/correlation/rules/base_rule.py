"""
Classe abstraite pour les règles de corrélation.
Toutes les règles héritent de BaseRule.
"""
from abc import ABC, abstractmethod
from typing import List

from django.db.models import QuerySet


class RuleMatch:
    """Résultat d'une évaluation de règle de corrélation."""

    def __init__(self, matched_logs: list, context: dict):
        self.matched_logs = matched_logs
        self.context = context

    def __bool__(self):
        return bool(self.matched_logs)


class BaseRule(ABC):
    """
    Interface commune pour toutes les règles de corrélation.
    """

    @abstractmethod
    def evaluate(self, logs: QuerySet, condition: dict) -> List[RuleMatch]:
        """
        Évalue la règle sur un ensemble de logs normalisés.

        Args:
            logs: QuerySet de NormalizedLog à analyser.
            condition: condition_logic JSONField de la CorrelationRule.

        Returns:
            Liste de RuleMatch, vide si aucune correspondance.
        """
        raise NotImplementedError
