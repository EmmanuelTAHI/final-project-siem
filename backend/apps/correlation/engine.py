"""
Moteur de corrélation multi-couches de Log+.
Exécute toutes les règles actives sur les nouveaux logs normalisés.
Réf. : Sheeraz et al., 2024 — Multi-layer SIEM Correlation Engine.
"""
import logging
from datetime import datetime

from django.db.models import QuerySet
from django.utils import timezone

from apps.correlation.models import CorrelationRule
from apps.correlation.rules.base_rule import RuleMatch
from apps.logs.models import NormalizedLog

logger = logging.getLogger(__name__)

# Mapping type de règle → classe d'implémentation
RULE_REGISTRY = {
    "threshold": "apps.correlation.rules.brute_force.BruteForceRule",
    "impossible_travel": "apps.correlation.rules.impossible_travel.ImpossibleTravelRule",
    "time_based": "apps.correlation.rules.off_hours_login.OffHoursLoginRule",
    "privilege_escalation": "apps.correlation.rules.privilege_escalation.PrivilegeEscalationRule",
    "mfa_bypass": "apps.correlation.rules.mfa_bypass.MFABypassRule",
    "wazuh_alert": "apps.correlation.rules.wazuh_alert.WazuhAlertRule",
    "lateral_movement": "apps.correlation.rules.lateral_movement.LateralMovementRule",
    "c2_beacon": "apps.correlation.rules.c2_beacon.C2BeaconRule",
    "data_exfil": "apps.correlation.rules.data_exfil.DataExfilRule",
}


def _import_rule_class(class_path: str):
    """Importe dynamiquement une classe de règle depuis son chemin."""
    module_path, class_name = class_path.rsplit(".", 1)
    module = __import__(module_path, fromlist=[class_name])
    return getattr(module, class_name)


class CorrelationEngine:
    """
    Moteur principal de corrélation.
    Tourne en boucle via Celery Beat toutes les 20 secondes.
    """

    def __init__(self):
        self.last_run_at: datetime | None = None

    def run(self, last_run_at: datetime | None = None) -> dict:
        """
        Lance le moteur de corrélation sur les logs depuis last_run_at.

        Args:
            last_run_at: Horodatage de la dernière exécution.
                         Si None, prend les logs des 5 dernières minutes.

        Returns:
            Dictionnaire de résultats : {alerts_created, rules_evaluated, matches_found}
        """
        from datetime import timedelta

        now = timezone.now()

        if last_run_at is None:
            last_run_at = now - timedelta(minutes=5)

        logger.info(
            "Moteur de corrélation démarré — logs depuis %s",
            last_run_at.isoformat(),
        )

        # Gate : ne rien faire s'il n'y a aucun log nouveau depuis le dernier run.
        new_count = NormalizedLog.objects.filter(indexed_at__gt=last_run_at).count()
        logger.info("Nouveaux logs depuis le dernier run : %d", new_count)
        if new_count == 0:
            return {"alerts_created": 0, "rules_evaluated": 0, "matches_found": 0}

        # Fenêtre d'analyse : les règles de seuil (brute force, etc.) doivent
        # agréger TOUTE leur fenêtre temporelle, pas seulement les logs indexés
        # depuis le dernier run — sinon N échecs répartis sur plusieurs runs ne
        # franchissent jamais le seuil. On fournit 24 h (couvre la plus longue
        # fenêtre de règle) ; chaque règle applique ensuite son propre filtre, et
        # _create_alert_if_new déduplique pour éviter de recréer la même alerte.
        analysis_logs = NormalizedLog.objects.filter(
            event_time__gte=now - timedelta(hours=24)
        )
        log_count = analysis_logs.count()

        # Charger les règles actives
        active_rules = CorrelationRule.objects.filter(is_active=True)
        rules_count = active_rules.count()
        logger.info("Règles actives : %d — logs dans la fenêtre : %d", rules_count, log_count)

        alerts_created = 0
        matches_found = 0

        for rule in active_rules:
            try:
                rule_matches = self._evaluate_rule(rule, analysis_logs)
                matches_found += len(rule_matches)

                for match in rule_matches:
                    alert = self._create_alert_if_new(rule, match, now)
                    if alert:
                        alerts_created += 1

            except Exception as exc:
                logger.exception("Erreur évaluation règle '%s' : %s", rule.name, exc)

        logger.info(
            "Moteur terminé — règles=%d, correspondances=%d, alertes créées=%d",
            rules_count,
            matches_found,
            alerts_created,
        )
        return {
            "alerts_created": alerts_created,
            "rules_evaluated": rules_count,
            "matches_found": matches_found,
            "logs_analyzed": log_count,
        }

    def _evaluate_rule(self, rule: CorrelationRule, logs: QuerySet) -> list[RuleMatch]:
        """
        Exécute une règle sur les logs et retourne les correspondances.
        Isolation multi-tenant : une règle ne doit JAMAIS être évaluée contre
        les logs d'une autre organisation que la sienne.
        """
        condition = rule.condition_logic
        rule_type = condition.get("type")

        if not rule_type:
            logger.warning("Règle '%s' sans 'type' dans condition_logic.", rule.name)
            return []

        rule_class_path = RULE_REGISTRY.get(rule_type)
        if not rule_class_path:
            logger.warning("Type de règle inconnu : '%s' (règle: %s)", rule_type, rule.name)
            return []

        org_logs = logs.filter(organization_id=rule.organization_id)

        rule_class = _import_rule_class(rule_class_path)
        rule_instance = rule_class()
        return rule_instance.evaluate(org_logs, condition)

    def _create_alert_if_new(self, rule: CorrelationRule, match: RuleMatch, now: datetime):
        """
        Crée une alerte si aucune alerte similaire n'est déjà ouverte.
        Déduplique sur (rule, user_email) avec statut open ou in_progress.
        Pour les règles Wazuh, la déduplication inclut le wazuh_rule_id, et pour
        Impossible Travel la paire de pays, afin de permettre plusieurs alertes
        distinctes pour le même user (évènements différents) sans qu'une seule
        alerte ouverte ne bloque toutes les suivantes.
        """
        from apps.alerts.models import Alert
        from apps.correlation.models import RuleMatch as RuleMatchModel

        user_email = match.context.get("user_email", "")
        wazuh_rule_id = match.context.get("wazuh_rule_id", "")
        country_1 = match.context.get("country_1", "")
        country_2 = match.context.get("country_2", "")

        # Déduplication : vérifier s'il existe déjà une alerte ouverte pour cette règle/user
        existing = Alert.objects.filter(
            rule=rule,
            status__in=("open", "in_progress"),
        )
        if user_email:
            existing = existing.filter(description__icontains=user_email)

        # Pour les règles Wazuh, affiner la dédup par wazuh_rule_id
        # pour permettre plusieurs alertes différentes pour le même user
        if wazuh_rule_id and existing.exists():
            existing = existing.filter(description__icontains=wazuh_rule_id)

        # Pour Impossible Travel, affiner par la paire de pays concernée :
        # FR↔US et US↔DE sont deux évènements distincts pour le même user.
        if country_1 and country_2 and existing.exists():
            existing = existing.filter(
                description__icontains=country_1
            ).filter(description__icontains=country_2)

        if existing.exists():
            logger.debug(
                "Alerte dédupliquée pour règle '%s' / user '%s' / wazuh_rule='%s'.",
                rule.name,
                user_email,
                wazuh_rule_id or "n/a",
            )
            return None

        # Générer le titre à partir du template
        try:
            title = rule.alert_title_template.format(**match.context)
        except KeyError:
            title = rule.alert_title_template

        # Construire la description
        description_lines = [
            f"Règle déclenchée : {rule.name}",
            f"Description : {rule.description}",
            "",
        ]
        for key, value in match.context.items():
            description_lines.append(f"• {key} : {value}")

        if rule.mitre_tactic:
            description_lines.append(f"\nMITRE Tactic : {rule.mitre_tactic}")
        if rule.mitre_technique:
            description_lines.append(f"MITRE Technique : {rule.mitre_technique}")

        alert = Alert.objects.create(
            title=title,
            description="\n".join(description_lines),
            severity=rule.severity,
            status="open",
            rule=rule,
            organization=rule.organization,
        )

        # Lier les logs à l'alerte
        if match.matched_logs:
            alert.source_logs.set(match.matched_logs)

        # Créer le RuleMatch
        rule_match_obj = RuleMatchModel.objects.create(rule=rule, alert=alert)
        rule_match_obj.logs.set(match.matched_logs)

        logger.info(
            "Alerte créée : [%s] %s (alert_id=%s)",
            rule.severity.upper(),
            title,
            alert.id,
        )
        return alert

    def test_rule(self, rule: CorrelationRule, max_logs: int = 1000) -> dict:
        """
        Teste une règle sur les N derniers logs normalisés.
        Utilisé par l'endpoint POST /api/correlation/rules/{id}/test/
        """
        from apps.logs.serializers import NormalizedLogBriefSerializer

        logs = NormalizedLog.objects.order_by("-event_time")[:max_logs]
        matches = self._evaluate_rule(rule, NormalizedLog.objects.filter(
            id__in=[l.id for l in logs]
        ))

        sample_logs = []
        if matches:
            for match in matches[:3]:
                for log in match.matched_logs[:2]:
                    sample_logs.append(NormalizedLogBriefSerializer(log).data)

        return {
            "matches_count": sum(len(m.matched_logs) for m in matches),
            "groups_matched": len(matches),
            "sample_logs": sample_logs,
        }


correlation_engine = CorrelationEngine()
