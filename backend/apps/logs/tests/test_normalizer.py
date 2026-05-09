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
