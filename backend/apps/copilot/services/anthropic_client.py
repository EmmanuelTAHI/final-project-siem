"""
Client Anthropic (Claude) minimal via httpx — pas de dépendance SDK, même
pattern que les autres clients threat intel (services/abuseipdb.py etc).
"""
import logging

import httpx
from django.conf import settings

logger = logging.getLogger(__name__)

ANTHROPIC_API_URL = "https://api.anthropic.com/v1/messages"
ANTHROPIC_VERSION = "2023-06-01"


def is_configured() -> bool:
    return bool(getattr(settings, "ANTHROPIC_API_KEY", ""))


def call_claude(
    messages: list[dict],
    system: str = "",
    tools: list[dict] | None = None,
    max_tokens: int = 1500,
) -> dict:
    """
    Appelle l'API Messages Anthropic. Retourne le JSON brut de la réponse
    (contient "content": [...] avec des blocks "text" et/ou "tool_use"),
    ou {} si la clé n'est pas configurée / en cas d'erreur réseau.
    """
    api_key = getattr(settings, "ANTHROPIC_API_KEY", "")
    if not api_key:
        logger.debug("ANTHROPIC_API_KEY non configurée — SOC Copilot désactivé")
        return {}

    payload = {
        "model": getattr(settings, "ANTHROPIC_MODEL", "claude-sonnet-4-5"),
        "max_tokens": max_tokens,
        "messages": messages,
    }
    if system:
        payload["system"] = system
    if tools:
        payload["tools"] = tools

    try:
        with httpx.Client(timeout=45.0) as client:
            resp = client.post(
                ANTHROPIC_API_URL,
                json=payload,
                headers={
                    "x-api-key": api_key,
                    "anthropic-version": ANTHROPIC_VERSION,
                    "content-type": "application/json",
                },
            )
            resp.raise_for_status()
            return resp.json()
    except httpx.HTTPError as exc:
        logger.warning("Appel Anthropic échoué : %s", exc)
        return {}
