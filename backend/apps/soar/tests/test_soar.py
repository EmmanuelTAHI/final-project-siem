"""Tests SOAR — Playbooks et exécutions."""
import uuid
from unittest.mock import MagicMock, patch

from django.test import TestCase
from django.contrib.auth import get_user_model

User = get_user_model()


class PlaybookModelTest(TestCase):
    def setUp(self):
        self.admin = User.objects.create_superuser(
            email="admin@test.ci", password="Test1234!", role="admin"
        )

    def test_playbook_creation(self):
        from apps.soar.models import Playbook
        pb = Playbook.objects.create(
            name="Test Playbook",
            description="Test",
            trigger_type="severity",
            trigger_conditions={"severities": ["critical"]},
            actions=[{"type": "send_email", "params": {"recipients": ["soc@test.ci"]}}],
            created_by=self.admin,
        )
        self.assertEqual(str(pb), "Test Playbook")
        self.assertTrue(pb.is_active)
        self.assertEqual(pb.execution_count, 0)

    def test_playbook_uuid_primary_key(self):
        from apps.soar.models import Playbook
        pb = Playbook.objects.create(name="UUID Test", created_by=self.admin)
        self.assertIsInstance(pb.id, uuid.UUID)


class ShouldTriggerTest(TestCase):
    def _make_alert(self, severity="critical", title="Test"):
        mock = MagicMock()
        mock.severity = severity
        mock.title = title
        mock.description = ""
        mock.rule_id = None
        return mock

    def test_severity_trigger_match(self):
        from apps.soar.tasks import _should_trigger
        pb = MagicMock()
        pb.trigger_type = "severity"
        pb.trigger_conditions = {"severities": ["critical", "high"]}
        alert = self._make_alert(severity="critical")
        self.assertTrue(_should_trigger(pb, alert))

    def test_severity_trigger_no_match(self):
        from apps.soar.tasks import _should_trigger
        pb = MagicMock()
        pb.trigger_type = "severity"
        pb.trigger_conditions = {"severities": ["critical"]}
        alert = self._make_alert(severity="low")
        self.assertFalse(_should_trigger(pb, alert))

    def test_cti_trigger(self):
        from apps.soar.tasks import _should_trigger
        pb = MagicMock()
        pb.trigger_type = "cti_match"
        pb.trigger_conditions = {}
        alert = self._make_alert(title="CTI: IP malveillante détectée")
        self.assertTrue(_should_trigger(pb, alert))


class SendEmailActionTest(TestCase):
    @patch("apps.soar.actions.send_email.send_mail")
    def test_send_email_success(self, mock_send):
        from apps.soar.actions import send_email
        mock_alert = MagicMock()
        mock_alert.title = "Test Alert"
        mock_alert.severity = "high"
        mock_alert.status = "open"
        mock_alert.created_at.strftime.return_value = "2026-04-26 10:00 UTC"

        result = send_email.execute(
            {"recipients": ["soc@test.ci"]}, mock_alert
        )
        self.assertEqual(result["status"], "success")
        mock_send.assert_called_once()

    def test_send_email_no_recipients(self):
        from apps.soar.actions import send_email
        result = send_email.execute({"recipients": []}, MagicMock())
        self.assertEqual(result["status"], "skipped")

    @patch("httpx.Client")
    def test_webhook_execute(self, mock_client_cls):
        from apps.soar.actions import webhook
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.raise_for_status = MagicMock()
        mock_client_cls.return_value.__enter__.return_value.request.return_value = mock_resp

        mock_alert = MagicMock()
        mock_alert.id = uuid.uuid4()
        mock_alert.title = "Test"
        mock_alert.severity = "high"
        mock_alert.status = "open"
        mock_alert.created_at.isoformat.return_value = "2026-04-26T10:00:00Z"
        mock_alert.description = "desc"

        result = webhook.execute({"url": "https://hooks.example.com/test"}, mock_alert)
        self.assertEqual(result["status"], "success")

    def test_webhook_no_url(self):
        from apps.soar.actions import webhook
        result = webhook.execute({}, MagicMock())
        self.assertEqual(result["status"], "skipped")
