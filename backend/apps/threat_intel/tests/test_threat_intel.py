"""Tests Threat Intelligence — ThreatIndicator, EnrichedLog, services CTI."""
import uuid
from unittest.mock import MagicMock, patch

from django.test import TestCase


class ThreatIndicatorTest(TestCase):
    def test_create_indicator(self):
        from apps.threat_intel.models import ThreatIndicator
        ind = ThreatIndicator.objects.create(
            indicator_type="ip",
            value="185.220.101.45",
            reputation_score=95.0,
            confidence=0.95,
            source="abuseipdb",
            is_malicious=True,
        )
        self.assertTrue(str(ind).startswith("[ip]"))
        self.assertIn("185.220.101.45", str(ind))

    def test_unique_together_constraint(self):
        from apps.threat_intel.models import ThreatIndicator
        from django.db import IntegrityError
        ThreatIndicator.objects.create(
            indicator_type="ip",
            value="1.2.3.4",
            source="abuseipdb",
        )
        with self.assertRaises(IntegrityError):
            ThreatIndicator.objects.create(
                indicator_type="ip",
                value="1.2.3.4",
                source="abuseipdb",
            )


class EnrichedLogTest(TestCase):
    def setUp(self):
        from django.utils import timezone
        from apps.logs.models import NormalizedLog, RawLog
        from apps.organizations.models import Organization
        self.org = Organization.objects.create(name="Test Org", slug="test-org")
        raw = RawLog.objects.create(
            organization=self.org, source_type="wazuh", raw_data={"_test": True},
        )
        self.log = NormalizedLog.objects.create(
            organization=self.org,
            raw_log=raw,
            event_time=timezone.now(),
            source_type="wazuh",
            action="Login",
            severity="warning",
            source_ip="185.220.101.45",
        )

    def test_compute_max_score(self):
        from apps.threat_intel.models import EnrichedLog, ThreatIndicator
        ind = ThreatIndicator.objects.create(
            indicator_type="ip",
            value="185.220.101.45",
            reputation_score=85.0,
            source="abuseipdb",
        )
        enriched = EnrichedLog.objects.create(log=self.log)
        enriched.indicators.add(ind)
        enriched.compute_max_score()
        self.assertEqual(enriched.max_score, 85.0)
        self.assertTrue(enriched.is_threat)

    def test_compute_max_score_no_threat(self):
        from apps.threat_intel.models import EnrichedLog, ThreatIndicator
        ind = ThreatIndicator.objects.create(
            indicator_type="ip",
            value="1.1.1.1",
            reputation_score=5.0,
            source="abuseipdb",
        )
        enriched = EnrichedLog.objects.create(log=self.log)
        enriched.indicators.add(ind)
        enriched.compute_max_score()
        self.assertFalse(enriched.is_threat)


class AbuseIPDBServiceTest(TestCase):
    @patch("apps.threat_intel.services.abuseipdb.httpx.Client")
    def test_check_ip_no_api_key(self, mock_client_cls):
        """Sans clé API, retourne dict vide sans appel HTTP."""
        from apps.threat_intel.services import abuseipdb
        with self.settings(ABUSEIPDB_API_KEY=""):
            result = abuseipdb.check_ip("185.220.101.45")
        self.assertEqual(result, {})
        mock_client_cls.assert_not_called()

    @patch("apps.threat_intel.services.abuseipdb.httpx.Client")
    def test_check_ip_with_api_key(self, mock_client_cls):
        """Avec une clé, effectue l'appel HTTP et retourne data."""
        mock_resp = MagicMock()
        mock_resp.raise_for_status = MagicMock()
        mock_resp.json.return_value = {
            "data": {"abuseConfidenceScore": 75, "countryCode": "RU"}
        }
        mock_client_cls.return_value.__enter__.return_value.get.return_value = mock_resp

        from apps.threat_intel.services import abuseipdb
        with self.settings(ABUSEIPDB_API_KEY="test-key-abc123"):
            result = abuseipdb.check_ip("185.220.101.45")
        self.assertEqual(result["abuseConfidenceScore"], 75)

    def test_get_malicious_score_virustotal(self):
        """Calcul score VT depuis stats."""
        from apps.threat_intel.services import virustotal
        vt_data = {
            "attributes": {
                "last_analysis_stats": {
                    "malicious": 10,
                    "suspicious": 2,
                    "harmless": 60,
                    "undetected": 28,
                }
            }
        }
        score = virustotal.get_malicious_score(vt_data)
        self.assertAlmostEqual(score, 10.0, places=0)

    def test_get_malicious_score_empty(self):
        from apps.threat_intel.services import virustotal
        self.assertEqual(virustotal.get_malicious_score({}), 0.0)
