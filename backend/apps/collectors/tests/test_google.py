"""
Tests du collecteur Google Workspace.
"""
import pytest


class TestGoogleCollectorMapping:
    """Tests du mapping des logs Google vers NormalizedLog."""

    def test_login_success_mapping(self):
        """Un log login_success Google doit être correctement mappé."""
        from apps.logs.normalizer import LogNormalizer

        raw_data = {
            "id": {
                "time": "2025-01-15T09:00:00.000Z",
                "uniqueQualifier": "12345",
                "applicationName": "login",
            },
            "actor": {
                "email": "guser@workspace.ci",
                "profileId": "google-profile-123",
            },
            "ipAddress": "41.202.100.50",
            "events": [
                {
                    "name": "login_success",
                    "parameters": [
                        {"name": "login_type", "value": "google_password"},
                        {"name": "is_suspicious", "boolValue": False},
                    ],
                }
            ],
            "_source": "google_workspace",
        }

        normalizer = LogNormalizer()
        result = normalizer._map_google(raw_data)

        assert result["action"] == "login_success"
        assert result["outcome"] == "success"
        assert result["user_email"] == "guser@workspace.ci"
        assert result["source_ip"] == "41.202.100.50"

    def test_login_failure_mapping(self):
        """Un log login_failure Google doit produire outcome=failure."""
        from apps.logs.normalizer import LogNormalizer

        raw_data = {
            "id": {"time": "2025-01-15T09:05:00.000Z"},
            "actor": {"email": "baduser@workspace.ci"},
            "ipAddress": "1.2.3.4",
            "events": [{"name": "login_failure", "parameters": []}],
            "_source": "google_workspace",
        }

        normalizer = LogNormalizer()
        result = normalizer._map_google(raw_data)

        assert result["action"] == "login_failure"
        assert result["outcome"] == "failure"

    def test_suspicious_login_blocked(self):
        """Un log suspicious_login_blocked doit avoir severity medium."""
        from apps.logs.normalizer import LogNormalizer

        raw_data = {
            "id": {"time": "2025-01-15T22:00:00.000Z"},
            "actor": {"email": "victim@workspace.ci"},
            "ipAddress": "200.100.50.10",
            "events": [{"name": "suspicious_login_blocked", "parameters": []}],
            "_source": "google_workspace",
        }

        normalizer = LogNormalizer()
        result = normalizer._map_google(raw_data)

        assert result["action"] == "suspicious_login_blocked"
        assert result["outcome"] == "failure"
