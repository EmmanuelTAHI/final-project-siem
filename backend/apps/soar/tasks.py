"""
Tâches Celery — déclenchement automatique des playbooks SOAR.
"""
import importlib
import logging

from celery import shared_task
from django.utils import timezone

logger = logging.getLogger(__name__)

ACTION_REGISTRY = {
    "send_email": "apps.soar.actions.send_email",
    "webhook": "apps.soar.actions.webhook",
    "block_ip": "apps.soar.actions.block_ip",
    "create_ticket": "apps.soar.actions.create_ticket",
    "create_internal_ticket": "apps.soar.actions.create_internal_ticket",
}


@shared_task(name="apps.soar.tasks.check_and_trigger_playbooks")
def check_and_trigger_playbooks():
    """
    Vérifie les alertes ouvertes et déclenche les playbooks applicables.
    Tourne toutes les 5 minutes via Celery Beat.
    """
    from apps.alerts.models import Alert
    from apps.soar.models import Playbook, PlaybookExecution

    active_playbooks = Playbook.objects.filter(is_active=True).prefetch_related()
    if not active_playbooks.exists():
        return {"triggered": 0}

    cutoff = timezone.now() - timezone.timedelta(minutes=6)
    new_alerts = Alert.objects.filter(status="open", created_at__gte=cutoff)

    triggered = 0
    for alert in new_alerts:
        for playbook in active_playbooks:
            if _should_trigger(playbook, alert):
                already_run = PlaybookExecution.objects.filter(
                    playbook=playbook, alert=alert
                ).exists()
                if not already_run:
                    execute_playbook.delay(str(playbook.id), str(alert.id))
                    triggered += 1

    logger.info("SOAR: %d playbooks déclenchés", triggered)
    return {"triggered": triggered}


def _should_trigger(playbook, alert) -> bool:
    """Évalue si un playbook doit se déclencher pour une alerte."""
    conditions = playbook.trigger_conditions
    trigger_type = playbook.trigger_type

    if trigger_type == "severity":
        allowed = conditions.get("severities", ["critical"])
        return alert.severity in allowed

    if trigger_type == "rule_match":
        rule_ids = conditions.get("rule_ids", [])
        return alert.rule_id and str(alert.rule_id) in [str(r) for r in rule_ids]

    if trigger_type == "ml_anomaly":
        return (
            alert.description
            and "anomalie" in alert.description.lower()
            and alert.severity in conditions.get("min_severity", ["high", "critical"])
        )

    if trigger_type == "cti_match":
        return "CTI" in (alert.title or "")

    return False


@shared_task(name="apps.soar.tasks.execute_playbook")
def execute_playbook(playbook_id: str, alert_id: str, triggered_by: str = "automatic"):
    """Exécute toutes les actions d'un playbook pour une alerte donnée."""
    from apps.alerts.models import Alert
    from apps.soar.models import Playbook, PlaybookExecution

    try:
        playbook = Playbook.objects.get(id=playbook_id)
        alert = Alert.objects.get(id=alert_id)
    except (Playbook.DoesNotExist, Alert.DoesNotExist) as exc:
        logger.error("execute_playbook: objet introuvable — %s", exc)
        return {"status": "failed", "error": str(exc)}

    execution = PlaybookExecution.objects.create(
        playbook=playbook,
        alert=alert,
        status="running",
        triggered_by=triggered_by,
    )

    actions_taken = []
    overall_success = True

    for action_def in playbook.actions:
        action_type = action_def.get("type", "")
        params = action_def.get("params", {})
        # Arrêt de la séquence si une étape précédente marquée
        # `stop_on_failure: true` a échoué — sans ça, un playbook linéaire
        # exécute TOUJOURS toutes ses actions même si la première (ex:
        # bloquer l'IP) a échoué, ce qui n'a pas de sens pour des actions
        # dépendantes (ex: ne notifier "IP bloquée" que si elle l'est vraiment).
        stop_on_failure = action_def.get("stop_on_failure", False)
        module_path = ACTION_REGISTRY.get(action_type)

        if not module_path:
            actions_taken.append({"type": action_type, "status": "skipped", "reason": "unknown_action_type"})
            continue

        try:
            module = importlib.import_module(module_path)
            result = module.execute(params, alert)
            actions_taken.append({"type": action_type, **result})
            if result.get("status") == "failed":
                overall_success = False
                if stop_on_failure:
                    actions_taken.append({"type": "_playbook", "status": "stopped", "reason": "stop_on_failure"})
                    break
        except Exception as exc:
            logger.exception("Action %s failed: %s", action_type, exc)
            actions_taken.append({"type": action_type, "status": "failed", "error": str(exc)})
            overall_success = False
            if stop_on_failure:
                actions_taken.append({"type": "_playbook", "status": "stopped", "reason": "stop_on_failure"})
                break

    execution.status = "success" if overall_success else "partial"
    execution.actions_taken = actions_taken
    execution.finished_at = timezone.now()
    execution.save(update_fields=["status", "actions_taken", "finished_at"])

    playbook.execution_count += 1
    playbook.save(update_fields=["execution_count"])

    logger.info(
        "Playbook '%s' exécuté pour alerte %s — %s",
        playbook.name, alert.id, execution.status,
    )
    return {"status": execution.status, "actions": actions_taken}
