"""
Outils d'ÉCRITURE exposés au SOC Copilot : créer/modifier des règles de
corrélation, des playbooks SOAR, des tickets, bloquer une IP, mettre à jour
une alerte. Puissant volontairement, mais avec deux limites dures, jamais
levées quel que soit l'outil ajouté ici :

1. TOUJOURS scopé à `organization_id` de l'utilisateur authentifié — jamais
   un paramètre fourni par le modèle, jamais d'accès cross-tenant.
2. AUCUNE exécution de code/commande arbitraire, aucune requête SQL/ORM
   libre — chaque action est une fonction dédiée avec des paramètres
   validés, pas un canal générique d'exécution.

Ces deux limites protègent contre l'injection de prompt indirecte : un
attaquant qui glisse une instruction dans un champ de log (user-agent,
hostname...) que le modèle lirait via query_logs ne peut PAS en sortir un
accès à d'autres organisations ni une exécution de code, seulement, au pire,
un déclenchement erroné d'une de ces actions bornées — toujours dans le
périmètre de l'organisation légitimement authentifiée.
"""
import logging

logger = logging.getLogger(__name__)

VALID_RULE_TYPES = [
    "threshold", "impossible_travel", "time_based", "privilege_escalation",
    "mfa_bypass", "wazuh_alert", "lateral_movement", "c2_beacon", "data_exfil",
    "web_attack_signature", "web_scan_detection", "security_scan_finding",
]

VALID_SEVERITIES = ["low", "medium", "high", "critical"]

WRITE_TOOL_SCHEMAS = [
    {
        "name": "create_correlation_rule",
        "description": (
            "Crée une nouvelle règle de corrélation/détection pour l'organisation. "
            "Utilise 'threshold' pour un seuil (ex: N échecs de connexion en X secondes), "
            "'time_based' pour une connexion hors horaires, 'impossible_travel' pour un "
            "déplacement géographique incohérent. Types disponibles : " + ", ".join(VALID_RULE_TYPES)
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "name": {"type": "string", "description": "Nom court et unique de la règle"},
                "description": {"type": "string"},
                "rule_type": {"type": "string", "enum": VALID_RULE_TYPES},
                "severity": {"type": "string", "enum": VALID_SEVERITIES},
                "alert_title_template": {
                    "type": "string",
                    "description": "Ex: 'Brute force détecté sur {user_email}'",
                },
                "count": {"type": "integer", "description": "Seuil de déclenchement (règles 'threshold')"},
                "window_seconds": {"type": "integer", "description": "Fenêtre glissante en secondes (règles 'threshold')"},
                "action_filter": {"type": "string", "description": "Ex: login_failure (règles 'threshold')"},
                "mitre_technique": {"type": "string", "description": "Ex: T1110"},
                "is_active": {"type": "boolean", "default": True},
            },
            "required": ["name", "description", "rule_type", "severity", "alert_title_template"],
        },
    },
    {
        "name": "update_correlation_rule",
        "description": "Modifie une règle de corrélation existante de l'organisation (seuil, sévérité, activation...).",
        "input_schema": {
            "type": "object",
            "properties": {
                "rule_id": {"type": "string"},
                "is_active": {"type": "boolean"},
                "severity": {"type": "string", "enum": VALID_SEVERITIES},
                "count": {"type": "integer"},
                "window_seconds": {"type": "integer"},
                "description": {"type": "string"},
            },
            "required": ["rule_id"],
        },
    },
    {
        "name": "create_soar_playbook",
        "description": (
            "Crée un playbook de réponse automatisée. Actions supportées : "
            "block_ip, send_email, webhook, create_ticket. Trigger : severity "
            "(déclenché par sévérité d'alerte) ou rule_match (règle précise)."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "name": {"type": "string"},
                "description": {"type": "string"},
                "trigger_type": {"type": "string", "enum": ["severity", "rule_match", "manual"]},
                "trigger_severities": {
                    "type": "array", "items": {"type": "string", "enum": VALID_SEVERITIES},
                    "description": "Sévérités qui déclenchent ce playbook (si trigger_type=severity)",
                },
                "actions": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "properties": {
                            "type": {"type": "string", "enum": ["block_ip", "send_email", "webhook", "create_ticket"]},
                            "params": {"type": "object"},
                        },
                        "required": ["type"],
                    },
                },
                "is_active": {"type": "boolean", "default": True},
            },
            "required": ["name", "trigger_type", "actions"],
        },
    },
    {
        "name": "block_ip",
        "description": "Bloque immédiatement une IP (applicatif ET réseau réel si le démon de blocage est configuré).",
        "input_schema": {
            "type": "object",
            "properties": {
                "ip_address": {"type": "string"},
                "reason": {"type": "string"},
                "duration_hours": {"type": "number", "description": "Durée du blocage en heures, absent = permanent"},
            },
            "required": ["ip_address", "reason"],
        },
    },
    {
        "name": "create_ticket",
        "description": "Crée un ticket SOC de suivi/investigation, optionnellement lié à une alerte.",
        "input_schema": {
            "type": "object",
            "properties": {
                "title": {"type": "string"},
                "description": {"type": "string"},
                "priority": {"type": "string", "enum": VALID_SEVERITIES},
                "alert_id": {"type": "string", "description": "UUID de l'alerte liée, optionnel"},
            },
            "required": ["title", "description", "priority"],
        },
    },
    {
        "name": "update_alert_status",
        "description": "Change le statut d'une alerte (open, in_progress, resolved, false_positive).",
        "input_schema": {
            "type": "object",
            "properties": {
                "alert_id": {"type": "string"},
                "status": {"type": "string", "enum": ["open", "in_progress", "resolved", "false_positive"]},
                "comment": {"type": "string"},
            },
            "required": ["alert_id", "status"],
        },
    },
]


# Outils dont l'endpoint API équivalent exige le rôle admin (pas seulement
# analyste) — répliqué ici pour que le Copilot ne devienne pas un moyen de
# contourner les permissions déjà en place sur les endpoints directs.
_ADMIN_ONLY_TOOLS = {"create_soar_playbook"}


def execute_write_tool(name: str, tool_input: dict, organization_id, user) -> dict:
    """Exécute un outil d'écriture, toujours scopé à `organization_id` (jamais celui fourni par l'IA)."""
    if name in _ADMIN_ONLY_TOOLS and getattr(user, "role", None) != "admin":
        return {"error": "Action réservée aux administrateurs de l'organisation."}

    handlers = {
        "create_correlation_rule": _create_correlation_rule,
        "update_correlation_rule": _update_correlation_rule,
        "create_soar_playbook": _create_soar_playbook,
        "block_ip": _block_ip,
        "create_ticket": _create_ticket,
        "update_alert_status": _update_alert_status,
    }
    handler = handlers.get(name)
    if not handler:
        return {"error": f"Outil d'écriture inconnu: {name}"}
    try:
        return handler(tool_input, organization_id, user)
    except Exception as exc:
        logger.exception("Échec de l'outil d'écriture Copilot '%s'", name)
        return {"error": f"Échec de l'action : {exc}"}


def _create_correlation_rule(tool_input: dict, organization_id, user) -> dict:
    from apps.correlation.models import CorrelationRule

    rule_type = tool_input.get("rule_type")
    if rule_type not in VALID_RULE_TYPES:
        return {"error": f"rule_type invalide, doit être l'un de : {VALID_RULE_TYPES}"}

    condition_logic = {"type": rule_type}
    if rule_type == "threshold":
        condition_logic["count"] = int(tool_input.get("count") or 5)
        condition_logic["window_seconds"] = int(tool_input.get("window_seconds") or 300)
        condition_logic["action"] = tool_input.get("action_filter") or "login_failure"

    rule, created = CorrelationRule.objects.update_or_create(
        organization_id=organization_id,
        name=tool_input["name"],
        defaults={
            "description": tool_input.get("description", ""),
            "severity": tool_input.get("severity", "medium"),
            "condition_logic": condition_logic,
            "alert_title_template": tool_input.get("alert_title_template", tool_input["name"]),
            "mitre_technique": tool_input.get("mitre_technique") or None,
            "is_active": tool_input.get("is_active", True),
            "created_by": user,
        },
    )
    return {"rule_id": str(rule.id), "created": created, "name": rule.name}


def _update_correlation_rule(tool_input: dict, organization_id, user) -> dict:
    from apps.correlation.models import CorrelationRule

    rule = CorrelationRule.objects.filter(id=tool_input["rule_id"], organization_id=organization_id).first()
    if not rule:
        return {"error": "Règle introuvable pour cette organisation."}

    if "is_active" in tool_input:
        rule.is_active = tool_input["is_active"]
    if "severity" in tool_input and tool_input["severity"] in VALID_SEVERITIES:
        rule.severity = tool_input["severity"]
    if "description" in tool_input:
        rule.description = tool_input["description"]
    if "count" in tool_input:
        rule.condition_logic["count"] = int(tool_input["count"])
    if "window_seconds" in tool_input:
        rule.condition_logic["window_seconds"] = int(tool_input["window_seconds"])
    rule.save()
    return {"rule_id": str(rule.id), "updated": True}


def _create_soar_playbook(tool_input: dict, organization_id, user) -> dict:
    from apps.soar.models import Playbook

    trigger_conditions = {}
    if tool_input.get("trigger_type") == "severity":
        trigger_conditions["severity"] = tool_input.get("trigger_severities") or ["critical", "high"]

    playbook, created = Playbook.objects.update_or_create(
        organization_id=organization_id,
        name=tool_input["name"],
        defaults={
            "description": tool_input.get("description", ""),
            "trigger_type": tool_input.get("trigger_type", "severity"),
            "trigger_conditions": trigger_conditions,
            "actions": tool_input.get("actions", []),
            "is_active": tool_input.get("is_active", True),
            "created_by": user,
        },
    )
    return {"playbook_id": str(playbook.id), "created": created, "name": playbook.name}


def _block_ip(tool_input: dict, organization_id, user) -> dict:
    from django.utils import timezone
    from datetime import timedelta

    from apps.soar.models import BlockedIP
    from apps.soar.views import _apply_real_block

    expires_at = None
    duration_hours = tool_input.get("duration_hours")
    if duration_hours:
        expires_at = timezone.now() + timedelta(hours=float(duration_hours))

    blocked = BlockedIP.objects.create(
        organization_id=organization_id,
        ip_address=tool_input["ip_address"],
        reason=tool_input.get("reason", "Bloqué via SOC Copilot"),
        source="manual",
        expires_at=expires_at,
    )
    network_result = _apply_real_block(blocked)
    return {"blocked_ip": blocked.ip_address, "network_block": network_result}


def _create_ticket(tool_input: dict, organization_id, user) -> dict:
    from django.db import transaction

    from apps.tickets.models import Ticket
    from apps.alerts.models import Alert

    alert = None
    alert_id = tool_input.get("alert_id")
    if alert_id:
        alert = Alert.objects.filter(id=alert_id, organization_id=organization_id).first()

    with transaction.atomic():
        last = (
            Ticket.objects.select_for_update()
            .filter(organization_id=organization_id)
            .order_by("-number")
            .first()
        )
        next_number = (last.number + 1) if last else 1
        ticket = Ticket.objects.create(
            organization_id=organization_id,
            number=next_number,
            title=tool_input["title"],
            description=tool_input.get("description", ""),
            priority=tool_input.get("priority", "medium"),
            alert=alert,
            reporter=user,
        )
    return {"ticket_id": str(ticket.id), "display_id": ticket.display_id}


def _update_alert_status(tool_input: dict, organization_id, user) -> dict:
    from apps.alerts.models import Alert

    alert = Alert.objects.filter(id=tool_input["alert_id"], organization_id=organization_id).first()
    if not alert:
        return {"error": "Alerte introuvable pour cette organisation."}

    new_status = tool_input.get("status")
    if new_status not in ["open", "in_progress", "resolved", "false_positive"]:
        return {"error": "Statut invalide."}

    alert.status = new_status
    alert.save(update_fields=["status"])
    return {"alert_id": str(alert.id), "status": alert.status}
