"""
Tests du service OAuth2 PKCE.
"""
import pytest
from unittest.mock import MagicMock, patch

from apps.authentication.services.oauth_service import OAuthService


class TestPKCEGeneration:
    """Tests de génération PKCE conforme RFC 7636."""

    def test_code_verifier_length(self):
        service = OAuthService()
        verifier = service.generate_code_verifier()
        # 96 octets base64url → environ 128 caractères
        assert 86 <= len(verifier) <= 128

    def test_code_verifier_uses_only_valid_chars(self):
        service = OAuthService()
        verifier = service.generate_code_verifier()
        import re
        # RFC 7636 : uniquement [A-Z], [a-z], [0-9], '-', '.', '_', '~'
        assert re.match(r'^[A-Za-z0-9\-._~]+$', verifier)

    def test_code_challenge_deterministic(self):
        """Le même verifier doit toujours produire le même challenge."""
        service = OAuthService()
        verifier = "test_verifier_12345"
        challenge1 = service.generate_code_challenge(verifier)
        challenge2 = service.generate_code_challenge(verifier)
        assert challenge1 == challenge2

    def test_code_challenge_sha256(self):
        """Vérifie que le challenge est bien SHA256(verifier) en base64url."""
        import base64
        import hashlib
        service = OAuthService()
        verifier = "dBjftJeZ4CVP-mB92K27uhbUJU1p1r_wW1gFWFOEjXk"
        digest = hashlib.sha256(verifier.encode()).digest()
        expected = base64.urlsafe_b64encode(digest).rstrip(b"=").decode()
        assert service.generate_code_challenge(verifier) == expected

    def test_state_is_64_chars_hex(self):
        service = OAuthService()
        state = service.generate_state()
        assert len(state) == 64
        assert all(c in "0123456789abcdef" for c in state)

    def test_two_states_are_different(self):
        service = OAuthService()
        assert service.generate_state() != service.generate_state()


class TestRedisStateStorage:
    """Tests du stockage Redis pour le state OAuth2."""

    @pytest.mark.django_db
    def test_store_and_retrieve_state(self, settings):
        """Le state stocké doit être récupérable et supprimé après lecture."""
        from django.core.cache import cache
        service = OAuthService()
        state = service.generate_state()
        verifier = service.generate_code_verifier()
        service.store_state(state, verifier)
        retrieved = service.retrieve_and_delete_state(state)
        assert retrieved == verifier
        # Deuxième appel doit retourner None (usage unique)
        assert service.retrieve_and_delete_state(state) is None

    @pytest.mark.django_db
    def test_unknown_state_returns_none(self):
        service = OAuthService()
        result = service.retrieve_and_delete_state("unknown_state_xyz_123")
        assert result is None
