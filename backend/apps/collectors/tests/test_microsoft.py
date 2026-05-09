"""
Tests du collecteur Microsoft 365.
"""
import pytest
from unittest.mock import MagicMock, patch


class TestMicrosoftCollectorMapping:
    """Tests du mapping des logs Microsoft vers NormalizedLog."""

    def test_login_success_mapping(self):
        """Un log avec errorCode=0 doit produire action=login_success, outcome=success."""
        from apps.logs.normalizer import LogNormalizer
        from apps.logs.models import RawLog

        raw_data = {
            "id": "test-123",
            "createdDateTime": "2025-01-15T10:30:00Z",
            "userPrincipalName": "user@contoso.com",
            "userDisplayName": "Test User",
            "ipAddress": "192.168.1.100",
            "location": {
                "city": "Abidjan",
                "countryOrRegion": "CI",
                "geoCoordinates": {"latitude": 5.35, "longitude": -4.0},
            },
            "status": {"errorCode": 0},
            "clientAppUsed": "Browser",
            "appDisplayName": "Microsoft Teams",
            "_source": "microsoft365",
        }

        normalizer = LogNormalizer()
        result = normalizer._map_microsoft(raw_data)

        assert result["action"] == "login_success"
        assert result["outcome"] == "success"
        assert result["user_email"] == "user@contoso.com"
        assert result["source_ip"] == "192.168.1.100"
        assert result["geo_country"] == "CI"
        assert result["severity"] == "info"

    def test_login_failure_mapping(self):
        """Un log avec errorCode!=0 doit produire action=login_failure, outcome=failure."""
        from apps.logs.normalizer import LogNormalizer

        raw_data = {
            "id": "test-456",
            "createdDateTime": "2025-01-15T11:00:00Z",
            "userPrincipalName": "attacker@contoso.com",
            "ipAddress": "10.0.0.1",
            "location": {"city": None, "countryOrRegion": "US", "geoCoordinates": {}},
            "status": {"errorCode": 50126, "failureReason": "Invalid credentials"},
            "clientAppUsed": "Mobile Apps and Desktop clients",
            "appDisplayName": "Exchange Online",
            "_source": "microsoft365",
        }

        normalizer = LogNormalizer()
        result = normalizer._map_microsoft(raw_data)

        assert result["action"] == "login_failure"
        assert result["outcome"] == "failure"
        assert result["severity"] == "medium"

    def test_missing_ip_handled_gracefully(self):
        """Un log sans IP ne doit pas lever d'exception."""
        from apps.logs.normalizer import LogNormalizer

        raw_data = {
            "id": "test-789",
            "createdDateTime": "2025-01-15T12:00:00Z",
            "userPrincipalName": "noip@contoso.com",
            "ipAddress": None,
            "location": {},
            "status": {"errorCode": 0},
            "_source": "microsoft365",
        }

        normalizer = LogNormalizer()
        result = normalizer._map_microsoft(raw_data)
        assert result["source_ip"] is None
