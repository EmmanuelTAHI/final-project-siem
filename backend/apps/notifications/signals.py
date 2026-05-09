"""
Signaux Django — broadcast WebSocket lors de la création/mise à jour d'alertes.
"""
import json
import logging

from asgiref.sync import async_to_sync
from channels.layers import get_channel_layer
from django.db.models.signals import post_save
from django.dispatch import receiver

logger = logging.getLogger(__name__)


def _broadcast_alert(alert, event_type: str):
    """Envoie une alerte via le channel layer Redis vers tous les consumers SOC."""
    channel_layer = get_channel_layer()
    if channel_layer is None:
        return

    alert_data = {
        "id": str(alert.id),
        "title": alert.title,
        "severity": alert.severity,
        "status": alert.status,
        "created_at": alert.created_at.isoformat(),
        "description": alert.description[:200],
    }

    try:
        async_to_sync(channel_layer.group_send)(
            "soc_global",
            {"type": event_type.replace("_", "."), "alert": alert_data},
        )
    except Exception as exc:
        logger.warning("WebSocket broadcast failed: %s", exc)


def connect_signals():
    """Appelé depuis AppConfig.ready() pour brancher les signaux."""
    from apps.alerts.models import Alert

    @receiver(post_save, sender=Alert, dispatch_uid="ws_new_alert")
    def on_alert_saved(sender, instance, created, **kwargs):
        if created:
            _broadcast_alert(instance, "new_alert")
        else:
            _broadcast_alert(instance, "alert_updated")
