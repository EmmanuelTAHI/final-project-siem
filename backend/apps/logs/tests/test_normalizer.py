"""
Tests du normaliseur de logs.
"""
import pytest
from datetime import datetime, timezone

from apps.logs.normalizer import LogNormalizer


class TestMicrosoftNormalization:
    """Tests du mapping Microsoft 365."""

    def test_login_success_fields(self):
        normalizer = LogNormalizer()
        data = {
            "createdDateTime": "2025-03-01T08:30:00Z",
            "userPrincipalName": "emp@corp.com",
            "ipAddress": "203.0.113.5",
            "location": {
                "city": "Paris",
                "countryOrRegion": "FR",
                "geoCoordinates": {"latitude": 48.85, "longitude": 2.35},
            },
            "status": {"errorCode": 0},
            "clientAppUsed": "Browser",
            "appDisplayName": "SharePoint",
            "_source": "microsoft365",
        }
        result = normalizer._map_microsoft(data)
        assert result["action"] == "login_success"
        assert result["outcome"] == "success"
        assert result["user_email"] == "emp@corp.com"
        assert result["geo_country"] == "FR"
        assert result["geo_city"] == "Paris"
        assert result["geo_latitude"] == 48.85
        assert result["severity"] == "info"

    def test_login_failure_severity(self):
        normalizer = LogNormalizer()
        data = {
            "createdDateTime": "2025-03-01T08:30:00Z",
            "userPrincipalName": "emp@corp.com",
            "ipAddress": "1.2.3.4",
            "location": {},
            "status": {"errorCode": 50126},
            "_source": "microsoft365",
        }
        result = normalizer._map_microsoft(data)
        assert result["severity"] == "medium"
        assert result["outcome"] == "failure"


class TestGoogleNormalization:
    """Tests du mapping Google Workspace."""

    def test_google_login_success(self):
        normalizer = LogNormalizer()
        data = {
            "id": {"time": "2025-03-01T09:00:00.000Z", "applicationName": "login"},
            "actor": {"email": "user@gw.ci", "profileId": "gp123"},
            "ipAddress": "196.168.1.5",
            "events": [{"name": "login_success", "parameters": []}],
            "_source": "google_workspace",
        }
        result = normalizer._map_google(data)
        assert result["action"] == "login_success"
        assert result["outcome"] == "success"
        assert result["user_email"] == "user@gw.ci"

    def test_google_logout_outcome(self):
        normalizer = LogNormalizer()
        data = {
            "id": {"time": "2025-03-01T17:00:00.000Z"},
            "actor": {"email": "user@gw.ci"},
            "ipAddress": "196.168.1.5",
            "events": [{"name": "logout", "parameters": []}],
            "_source": "google_workspace",
        }
        result = normalizer._map_google(data)
        assert result["outcome"] == "success"


class TestWazuhNormalization:
    """Tests du mapping Wazuh."""

    def test_wazuh_level_to_severity(self):
        normalizer = LogNormalizer()
        data = {
            "timestamp": "2025-03-01T10:00:00Z",
            "rule": {"id": "5710", "description": "Attempt to login...", "level": 12},
            "agent": {"id": "001", "name": "web-server", "ip": "10.0.0.5"},
            "data": {"srcip": "185.100.200.50"},
            "_source": "wazuh",
        }
        result = normalizer._map_wazuh(data)
        assert result["severity"] == "high"
        assert result["source_ip"] == "185.100.200.50"

    def test_wazuh_critical_level(self):
        normalizer = LogNormalizer()
        data = {
            "timestamp": "2025-03-01T10:00:00Z",
            "rule": {"id": "0099", "description": "Rootkit detected", "level": 15},
            "agent": {"id": "002", "name": "db-server"},
            "data": {},
            "_source": "wazuh",
        }
        result = normalizer._map_wazuh(data)
        assert result["severity"] == "critical"


class TestSyslogNormalization:
    """Non-régression : le format syslog brut (rsyslog, receive_syslog) doit
    continuer à fonctionner exactement comme avant l'ajout du support JSON
    de l'agent natif (dispatch dans _map_syslog)."""

    def test_raw_syslog_line_unaffected(self):
        normalizer = LogNormalizer()
        data = {
            "severity": "warning",
            "severity_code": 4,
            "facility": "auth",
            "message": "some raw syslog message",
            "source_ip": "10.0.0.9",
            "received_at": "2025-03-01T10:00:00Z",
            "raw_message": "<36>some raw syslog message",
        }
        result = normalizer._map_syslog(data)
        assert result["action"] == "syslog_auth"
        assert result["source_ip"] == "10.0.0.9"
        assert result["extra_fields"]["facility"] == "auth"

    def test_ssh_brute_force_detection_unaffected(self):
        normalizer = LogNormalizer()
        data = {
            "severity": "warning",
            "facility": "auth",
            "message": "Failed password for admin from 1.2.3.4 port 40222 ssh2",
            "source_ip": "1.2.3.4",
            "received_at": "2025-03-01T10:00:00Z",
        }
        result = normalizer._map_syslog(data)
        assert result["action"] == "login_failure"
        assert result["user_email"] == "admin"
        assert result["source_ip"] == "1.2.3.4"
        assert result["severity"] == "high"


class TestAgentJsonNormalization:
    """Agent Log+ natif : lignes JSON structurées (agent_format='json'),
    routées par _map_syslog vers _map_agent_json."""

    def test_windows_login_failure_event_4625(self):
        normalizer = LogNormalizer()
        data = {
            "agent_format": "json",
            "message": "An account failed to log on.",
            "hostname": "WIN-DESKTOP-01",
            "severity": "info",
            "source": "wineventlog",
            "event_id": 4625,
            "provider": "Microsoft-Windows-Security-Auditing",
            "channel": "Security",
            "computer": "WIN-DESKTOP-01",
            "time_created": "2026-07-20T10:00:00Z",
            "source_ip": "198.51.100.7",
            "raw_fields": {"TargetUserName": "jdupont", "LogonType": "3"},
        }
        result = normalizer._map_agent_json(data)
        assert result["action"] == "login_failure"
        assert result["outcome"] == "failure"
        assert result["user_email"] == "jdupont"
        assert result["severity"] == "high"
        assert result["resource"] == "WIN-DESKTOP-01"
        assert result["extra_fields"]["event_id"] == 4625
        assert result["extra_fields"]["provider"] == "Microsoft-Windows-Security-Auditing"

    def test_windows_login_success_event_4624(self):
        normalizer = LogNormalizer()
        data = {
            "agent_format": "json",
            "message": "An account was successfully logged on.",
            "hostname": "WIN-DESKTOP-01",
            "source": "wineventlog",
            "event_id": 4624,
            "provider": "Microsoft-Windows-Security-Auditing",
            "raw_fields": {"TargetUserName": "jdupont"},
        }
        result = normalizer._map_agent_json(data)
        assert result["action"] == "login_success"
        assert result["outcome"] == "success"
        assert result["user_email"] == "jdupont"

    def test_linux_agent_ssh_brute_force_still_detected(self):
        """Le collecteur Linux natif (tail de fichier / journald / relais
        syslog) doit continuer à alimenter la règle brute force, exactement
        comme le faisait déjà le chemin syslog historique."""
        normalizer = LogNormalizer()
        data = {
            "agent_format": "json",
            "message": "Failed password for admin from 1.2.3.4 port 40222 ssh2",
            "hostname": "srv-linux-01",
            "severity": "info",
            "source": "linuxlog",
        }
        result = normalizer._map_agent_json(data)
        assert result["action"] == "login_failure"
        assert result["outcome"] == "failure"
        assert result["user_email"] == "admin"
        assert result["source_ip"] == "1.2.3.4"
        assert result["severity"] == "high"

    def test_generic_linux_agent_event_no_special_mapping(self):
        normalizer = LogNormalizer()
        data = {
            "agent_format": "json",
            "message": "some structured linux event",
            "hostname": "srv-linux-01",
            "severity": "medium",
            "source": "linuxlog",
        }
        result = normalizer._map_agent_json(data)
        assert result["action"] == "linuxlog"
        assert result["outcome"] == "unknown"
        assert result["resource"] == "srv-linux-01"
        assert result["severity"] == "medium"

    def test_dispatch_from_map_syslog_routes_json(self):
        """_map_syslog (le mapper enregistré pour source_type='agent') doit
        détecter agent_format='json' et déléguer, sans jamais tenter de
        parser le message comme une ligne syslog brute."""
        normalizer = LogNormalizer()
        data = {
            "agent_format": "json",
            "message": "structured event",
            "hostname": "host1",
            "source": "wineventlog",
            "event_id": 1000,
            "provider": "SomeOtherProvider",
        }
        result = normalizer._map_syslog(data)
        assert result["extra_fields"]["event_id"] == 1000
