"""Tests WebSocket Consumer notifications."""
import json
from unittest.mock import AsyncMock, MagicMock, patch

from django.test import TestCase


class AlertNotificationConsumerTest(TestCase):
    """Tests unitaires du consumer WebSocket — sans couche Channels complète."""

    def _make_consumer(self, user_id="42"):
        from apps.notifications.consumers import AlertNotificationConsumer
        consumer = AlertNotificationConsumer()
        consumer.scope = {"url_route": {"kwargs": {"user_id": user_id}}}
        consumer.channel_name = "test_channel"
        consumer.channel_layer = AsyncMock()
        consumer.send = AsyncMock()
        consumer.accept = AsyncMock()
        return consumer

    def test_consumer_instantiation(self):
        from apps.notifications.consumers import AlertNotificationConsumer
        consumer = AlertNotificationConsumer()
        self.assertIsNotNone(consumer)

    def test_new_alert_handler_sends_json(self):
        import asyncio
        consumer = self._make_consumer()
        event = {"alert": {"id": "1", "title": "Test", "severity": "high"}}

        asyncio.get_event_loop().run_until_complete(consumer.new_alert(event))
        consumer.send.assert_called_once()
        call_args = consumer.send.call_args
        sent_data = json.loads(call_args.kwargs.get("text_data") or call_args.args[0])
        self.assertEqual(sent_data["type"], "new_alert")
        self.assertEqual(sent_data["alert"]["title"], "Test")

    def test_system_notification_with_notification_key(self):
        import asyncio
        consumer = self._make_consumer()
        event = {"notification": {"message": "Account linked", "level": "info"}}

        asyncio.get_event_loop().run_until_complete(consumer.system_notification(event))
        call_args = consumer.send.call_args
        sent_data = json.loads(call_args.kwargs.get("text_data") or call_args.args[0])
        self.assertEqual(sent_data["type"], "security_notification")

    def test_ping_pong(self):
        import asyncio
        consumer = self._make_consumer()
        asyncio.get_event_loop().run_until_complete(
            consumer.receive(text_data=json.dumps({"type": "ping"}))
        )
        call_args = consumer.send.call_args
        sent_data = json.loads(call_args.kwargs.get("text_data") or call_args.args[0])
        self.assertEqual(sent_data["type"], "pong")

    def test_invalid_json_receive(self):
        import asyncio
        consumer = self._make_consumer()
        asyncio.get_event_loop().run_until_complete(
            consumer.receive(text_data="not valid json")
        )
        consumer.send.assert_not_called()
