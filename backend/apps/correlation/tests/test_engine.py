"""
Tests du moteur de corrélation et des règles.
"""
import pytest
from datetime import timedelta
from unittest.mock import MagicMock, patch

from django.utils import timezone


@pytest.fixture
def org(db):
    from apps.organizations.models import Organization
    return Organization.objects.create(name="Test Org", slug="test-org")


@pytest.fixture
def make_normalized_log(db, org):
    """Factory pour créer des NormalizedLog de test."""
    from apps.logs.models import NormalizedLog, RawLog
    from apps.collectors.models import ConnectorConfig
    from apps.users.models import User

    def _make(
        action="login_success",
        outcome="success",
        user_email="user@test.ci",
        source_ip="1.2.3.4",
        geo_country="CI",
        geo_city="Abidjan",
        event_time=None,
        severity="info",
        extra_fields=None,
    ):
        if event_time is None:
            event_time = timezone.now()

        raw = RawLog.objects.create(
            organization=org,
            source_type="microsoft365",
            raw_data={"_test": True},
        )
        return NormalizedLog.objects.create(
            organization=org,
            raw_log=raw,
            event_time=event_time,
            source_type="microsoft365",
            action=action,
            outcome=outcome,
            user_email=user_email,
            source_ip=source_ip,
            geo_country=geo_country,
            geo_city=geo_city,
            severity=severity,
            extra_fields=extra_fields or {},
        )

    return _make


class TestBruteForceRule:
    """Tests de la règle Brute Force."""

    def test_detects_brute_force(self, db, make_normalized_log):
        from apps.correlation.rules.brute_force import BruteForceRule
        from apps.logs.models import NormalizedLog

        # Créer 6 login_failure pour le même utilisateur
        for _ in range(6):
            make_normalized_log(
                action="login_failure",
                outcome="failure",
                user_email="victim@corp.com",
            )

        rule = BruteForceRule()
        condition = {
            "type": "threshold",
            "field": "user_email",
            "action": "login_failure",
            "count": 5,
            "window_seconds": 300,
        }
        matches = rule.evaluate(NormalizedLog.objects.all(), condition)
        assert len(matches) == 1
        assert matches[0].context["user_email"] == "victim@corp.com"
        assert matches[0].context["failure_count"] >= 5

    def test_no_brute_force_below_threshold(self, db, make_normalized_log):
        from apps.correlation.rules.brute_force import BruteForceRule
        from apps.logs.models import NormalizedLog

        # Créer seulement 3 login_failure (< seuil de 5)
        for _ in range(3):
            make_normalized_log(action="login_failure", outcome="failure")

        rule = BruteForceRule()
        condition = {"type": "threshold", "field": "user_email", "action": "login_failure", "count": 5, "window_seconds": 300}
        matches = rule.evaluate(NormalizedLog.objects.all(), condition)
        assert len(matches) == 0


class TestImpossibleTravelRule:
    """Tests de la règle Impossible Travel."""

    def test_detects_impossible_travel(self, db, make_normalized_log):
        from apps.correlation.rules.impossible_travel import ImpossibleTravelRule
        from apps.logs.models import NormalizedLog

        now = timezone.now()
        make_normalized_log(
            action="login_success",
            user_email="traveler@corp.com",
            geo_country="CI",
            geo_city="Abidjan",
            event_time=now - timedelta(minutes=30),
        )
        make_normalized_log(
            action="login_success",
            user_email="traveler@corp.com",
            geo_country="US",
            geo_city="New York",
            event_time=now - timedelta(minutes=5),
        )

        rule = ImpossibleTravelRule()
        condition = {"type": "impossible_travel", "window_seconds": 7200}
        matches = rule.evaluate(NormalizedLog.objects.all(), condition)
        assert len(matches) == 1
        assert matches[0].context["user_email"] == "traveler@corp.com"
        assert matches[0].context["country_1"] != matches[0].context["country_2"]

    def test_no_alert_same_country(self, db, make_normalized_log):
        from apps.correlation.rules.impossible_travel import ImpossibleTravelRule
        from apps.logs.models import NormalizedLog

        now = timezone.now()
        make_normalized_log(action="login_success", user_email="local@corp.com", geo_country="CI", event_time=now - timedelta(minutes=30))
        make_normalized_log(action="login_success", user_email="local@corp.com", geo_country="CI", event_time=now - timedelta(minutes=10))

        rule = ImpossibleTravelRule()
        matches = rule.evaluate(NormalizedLog.objects.all(), {"type": "impossible_travel", "window_seconds": 7200})
        assert len(matches) == 0


class TestOffHoursLoginRule:
    """Tests de la règle Off-Hours Login."""

    def test_detects_off_hours(self, db, make_normalized_log):
        from apps.correlation.rules.off_hours_login import OffHoursLoginRule
        from apps.logs.models import NormalizedLog

        # Créer une connexion à 22h UTC (hors-bureau)
        night_time = timezone.now().replace(hour=22, minute=0, second=0, microsecond=0)
        make_normalized_log(
            action="login_success",
            user_email="night@corp.com",
            event_time=night_time,
        )

        rule = OffHoursLoginRule()
        condition = {"type": "time_based", "action": "login_success", "forbidden_hours_start": 20, "forbidden_hours_end": 7}
        matches = rule.evaluate(NormalizedLog.objects.all(), condition)
        assert len(matches) >= 1
