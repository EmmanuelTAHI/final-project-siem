"""
Signaux Django — broadcast WebSocket lors de la création/mise à jour d'alertes.
"""
import logging

from asgiref.sync import async_to_sync
from channels.layers import get_channel_layer
from django.db import transaction
from django.db.models.signals import post_save

logger = logging.getLogger(__name__)


def _serialize_alert(alert) -> dict:
    """
    Payload complet aligné sur le type Alert du frontend : le client peut
    insérer l'alerte dans la liste sans requête supplémentaire.
    """
    first_log = None
    event_count = 0
    try:
        logs = list(alert.source_logs.all()[:1])
        first_log = logs[0] if logs else None
        event_count = alert.source_logs.count()
    except Exception:  # M2M pas encore disponible (création en cours)
        pass

    rule = alert.rule
    return {
        "id": str(alert.id),
        "title": alert.title,
        "description": alert.description[:300],
        "severity": alert.severity,
        "status": alert.status,
        "rule_id": str(rule.id) if rule else None,
        "rule_name": rule.name if rule else None,
        "mitre_tactic": getattr(rule, "mitre_tactic", None) if rule else None,
        "mitre_technique": getattr(rule, "mitre_technique", None) if rule else None,
        "event_count": event_count,
        "source_ip": getattr(first_log, "source_ip", None),
        "user_email": getattr(first_log, "user_email", None),
        "assigned_to": str(alert.assigned_to_id) if alert.assigned_to_id else None,
        "assigned_to_name": alert.assigned_to.email if alert.assigned_to_id else None,
        "created_at": alert.created_at.isoformat(),
        "updated_at": alert.updated_at.isoformat(),
        "resolved_at": alert.resolved_at.isoformat() if alert.resolved_at else None,
    }


def _broadcast_alert(alert, event_type: str):
    """Envoie une alerte via le channel layer Redis vers tous les consumers SOC."""
    channel_layer = get_channel_layer()
    if channel_layer is None:
        return

    try:
        alert_data = _serialize_alert(alert)
        async_to_sync(channel_layer.group_send)(
            "soc_global",
            {"type": event_type.replace("_", "."), "alert": alert_data},
        )
    except Exception as exc:
        logger.warning("WebSocket broadcast failed: %s", exc)


def _on_alert_saved(sender, instance, created, **kwargs):
    """
    Receiver module-level (référence forte : ne peut pas être garbage-collecté
    comme le serait une fonction locale connectée avec weak=True).
    """
    event = "new_alert" if created else "alert_updated"
    # on_commit : le broadcast part après le COMMIT de la transaction. Sinon le
    # client reçoit l'évènement, refetch la liste... et la base ne contient pas
    # encore l'alerte (ni ses source_logs M2M).
    transaction.on_commit(lambda: _broadcast_alert(instance, event))


def connect_signals():
    """Appelé depuis AppConfig.ready() pour brancher les signaux."""
    from apps.alerts.models import Alert

    # weak=False : le receiver reste connecté même si aucune autre référence
    # forte ne subsiste (indispensable ici — sans ça le signal se déconnecte
    # silencieusement et aucune alerte n'est diffusée en temps réel).
    post_save.connect(
        _on_alert_saved,
        sender=Alert,
        dispatch_uid="ws_alert_broadcast",
        weak=False,
    )
