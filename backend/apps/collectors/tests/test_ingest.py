"""
Tests de l'endpoint d'ingestion agent (POST /api/ingest/agent/logs/) et de
sa détection JSON vs syslog brut par ligne (agent Log+ natif, session
2026-07-20).
"""
import hashlib
import secrets

import pytest
from rest_framework import status
from rest_framework.test import APIClient

from apps.collectors.authentication import TOKEN_PREFIX
from apps.collectors.ingest_views import AgentLogIngestView
from apps.collectors.models import AgentEnrollmentToken
from apps.logs.models import RawLog
from apps.organizations.models import Organization


class TestParseLine:
    """Unitaire : _parse_line doit router JSON structuré vs syslog brut."""

    def test_json_line_is_tagged_and_preserved(self):
        line = '{"message": "hello", "event_id": 4625, "provider": "Microsoft-Windows-Security-Auditing"}'
        result = AgentLogIngestView._parse_line(line, "10.0.0.5")
        assert result["agent_format"] == "json"
        assert result["message"] == "hello"
        assert result["event_id"] == 4625
        assert result["source_ip"] == "10.0.0.5"
        assert "received_at" in result

    def test_raw_syslog_line_falls_back_unchanged(self):
        line = "<34>Failed password for admin from 1.2.3.4 port 40222 ssh2"
        result = AgentLogIngestView._parse_line(line, "1.2.3.4")
        assert "agent_format" not in result
        assert "Failed password" in result["message"]

    def test_malformed_json_falls_back_to_syslog_parsing(self):
        line = '{"message": "unterminated'
        result = AgentLogIngestView._parse_line(line, "1.2.3.4")
        assert "agent_format" not in result
        # Pas de crash : la ligne brute devient le message syslog.
        assert result["message"]

    def test_json_array_not_treated_as_structured_event(self):
        """Un JSON valide mais pas un objet (ex: une liste) ne doit pas être
        traité comme un évènement structuré — retombe sur le parsing syslog."""
        line = '["not", "a", "dict"]'
        result = AgentLogIngestView._parse_line(line, "1.2.3.4")
        assert "agent_format" not in result


@pytest.fixture
def org(db):
    return Organization.objects.create(name="Test Org", slug="test-org")


@pytest.fixture
def agent_token(db, org):
    """Réplique exactement la génération de apps/collectors/views.py pour
    obtenir un vrai token utilisable via AgentTokenAuthentication."""
    raw_secret = secrets.token_urlsafe(32)
    token = AgentEnrollmentToken.objects.create(
        organization=org,
        name="Test token",
        token_prefix=raw_secret[:8],
        token_hash=hashlib.sha256(raw_secret.encode()).hexdigest(),
        is_active=True,
    )
    return token, f"{TOKEN_PREFIX}{raw_secret}"


class TestAgentLogIngestView:
    """Intégration : POST /api/ingest/agent/logs/ avec un vrai token."""

    def test_json_line_creates_raw_log_with_agent_source_type(self, db, agent_token):
        token, full_token = agent_token
        client = APIClient()
        body = '{"message": "test event", "event_id": 4624, "provider": "Microsoft-Windows-Security-Auditing"}\n'
        response = client.post(
            "/api/ingest/agent/logs/",
            data=body,
            content_type="text/plain",
            HTTP_AUTHORIZATION=f"Bearer {full_token}",
        )
        assert response.status_code == status.HTTP_201_CREATED
        assert response.data["data"]["accepted"] == 1

        raw_log = RawLog.objects.get(organization=token.organization)
        assert raw_log.source_type == "agent"
        assert raw_log.raw_data["agent_format"] == "json"
        assert raw_log.raw_data["event_id"] == 4624

    def test_invalid_token_rejected(self, db, org):
        """Token bien formé mais inconnu : AuthenticationFailed levée par
        l'authenticator -> 403 (pas de authenticate_header défini, DRF ne
        renvoie donc pas 401 dans ce cas)."""
        client = APIClient()
        response = client.post(
            "/api/ingest/agent/logs/",
            data="hello\n",
            content_type="text/plain",
            HTTP_AUTHORIZATION=f"Bearer {TOKEN_PREFIX}not-a-real-token-00000000",
        )
        assert response.status_code == status.HTTP_403_FORBIDDEN

    def test_missing_token_rejected(self, db):
        """Aucun header Authorization : l'authenticator renvoie None (pas
        d'exception), donc request.user est anonyme et c'est la vue elle-même
        (pas DRF) qui renvoie 401 explicitement — voir AgentLogIngestView.post."""
        client = APIClient()
        response = client.post(
            "/api/ingest/agent/logs/",
            data="hello\n",
            content_type="text/plain",
        )
        assert response.status_code == status.HTTP_401_UNAUTHORIZED

    def test_revoked_token_rejected(self, db, agent_token):
        token, full_token = agent_token
        token.is_active = False
        token.save(update_fields=["is_active"])

        client = APIClient()
        response = client.post(
            "/api/ingest/agent/logs/",
            data="hello\n",
            content_type="text/plain",
            HTTP_AUTHORIZATION=f"Bearer {full_token}",
        )
        assert response.status_code == status.HTTP_403_FORBIDDEN

    def test_second_organization_never_sees_first_organizations_logs(self, db, agent_token):
        """Isolation multi-tenant : un token d'une organisation ne doit
        jamais pouvoir écrire ni laisser fuiter des logs vers une autre."""
        token_a, full_token_a = agent_token
        org_b = Organization.objects.create(name="Org B", slug="org-b")
        raw_secret_b = secrets.token_urlsafe(32)
        AgentEnrollmentToken.objects.create(
            organization=org_b,
            name="Org B token",
            token_prefix=raw_secret_b[:8],
            token_hash=hashlib.sha256(raw_secret_b.encode()).hexdigest(),
            is_active=True,
        )
        full_token_b = f"{TOKEN_PREFIX}{raw_secret_b}"

        client = APIClient()
        client.post(
            "/api/ingest/agent/logs/", data="from org A\n", content_type="text/plain",
            HTTP_AUTHORIZATION=f"Bearer {full_token_a}",
        )
        client.post(
            "/api/ingest/agent/logs/", data="from org B\n", content_type="text/plain",
            HTTP_AUTHORIZATION=f"Bearer {full_token_b}",
        )

        assert RawLog.objects.filter(organization=token_a.organization).count() == 1
        assert RawLog.objects.filter(organization=org_b).count() == 1
        assert not RawLog.objects.filter(organization=token_a.organization, raw_data__raw_message__icontains="org B").exists()

    def test_plain_syslog_line_still_works_end_to_end(self, db, agent_token):
        """Non-régression : un agent existant (rsyslog/NXLog) envoyant du
        RFC3164 brut continue de fonctionner exactement comme avant."""
        token, full_token = agent_token
        client = APIClient()
        response = client.post(
            "/api/ingest/agent/logs/",
            data="<34>Failed password for admin from 1.2.3.4 port 40222 ssh2\n",
            content_type="text/plain",
            HTTP_AUTHORIZATION=f"Bearer {full_token}",
        )
        assert response.status_code == status.HTTP_201_CREATED
        raw_log = RawLog.objects.get(organization=token.organization)
        assert "agent_format" not in raw_log.raw_data
        assert "Failed password" in raw_log.raw_data["message"]
