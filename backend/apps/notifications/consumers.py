"""
Django Channels — WebSocket consumer pour les notifications temps réel SOC.
"""
import json
import logging

from channels.generic.websocket import AsyncWebsocketConsumer

logger = logging.getLogger(__name__)


class AlertNotificationConsumer(AsyncWebsocketConsumer):
    """
    WebSocket consumer pour les alertes temps réel.
    Chaque utilisateur authentifié rejoint son groupe personnel + le groupe global SOC.
    """

    async def connect(self):
        self.user_id = self.scope["url_route"]["kwargs"].get("user_id", "anonymous")
        self.user_group = f"user_{self.user_id}"
        self.soc_group = "soc_global"

        await self.channel_layer.group_add(self.user_group, self.channel_name)
        await self.channel_layer.group_add(self.soc_group, self.channel_name)
        await self.accept()
        logger.debug("WS connect: user=%s", self.user_id)

        await self.send(text_data=json.dumps({
            "type": "connection_established",
            "message": "Connecté aux notifications Log+ en temps réel",
        }))

    async def disconnect(self, close_code):
        await self.channel_layer.group_discard(self.user_group, self.channel_name)
        await self.channel_layer.group_discard(self.soc_group, self.channel_name)
        logger.debug("WS disconnect: user=%s code=%s", self.user_id, close_code)

    async def receive(self, text_data):
        """Permet au client d'envoyer un ping ou de s'abonner à des filtres."""
        try:
            data = json.loads(text_data)
            if data.get("type") == "ping":
                await self.send(text_data=json.dumps({"type": "pong"}))
        except (json.JSONDecodeError, KeyError):
            pass

    # ── Handlers de messages envoyés depuis le serveur ──────────────────────────

    async def new_alert(self, event):
        """Nouvelle alerte créée — broadcast à tous les analystes SOC."""
        await self.send(text_data=json.dumps({
            "type": "new_alert",
            "alert": event["alert"],
        }))

    async def alert_updated(self, event):
        """Alerte mise à jour (statut, assignation...)."""
        await self.send(text_data=json.dumps({
            "type": "alert_updated",
            "alert": event["alert"],
        }))

    async def cti_threat_detected(self, event):
        """Menace CTI détectée."""
        await self.send(text_data=json.dumps({
            "type": "cti_threat",
            "data": event["data"],
        }))

    async def playbook_executed(self, event):
        """Playbook SOAR exécuté."""
        await self.send(text_data=json.dumps({
            "type": "playbook_executed",
            "data": event["data"],
        }))

    async def system_notification(self, event):
        """Notification système / sécurité (compte lié, brute force, etc.)."""
        if "notification" in event:
            await self.send(text_data=json.dumps({
                "type": "security_notification",
                "notification": event["notification"],
            }))
        else:
            await self.send(text_data=json.dumps({
                "type": "system",
                "message": event.get("message"),
                "level": event.get("level", "info"),
            }))
