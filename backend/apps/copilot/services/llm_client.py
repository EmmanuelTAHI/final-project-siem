"""
Dispatch du SOC Copilot vers le fournisseur IA configuré : Anthropic Claude
en priorité (qualité de tool-use supérieure), sinon Google Gemini (AI Studio)
en repli gratuit. Les deux clients exposent le même format d'entrée/sortie.
"""
from . import anthropic_client, gemini_client


def is_configured() -> bool:
    return anthropic_client.is_configured() or gemini_client.is_configured()


def call_llm(
    messages: list[dict],
    system: str = "",
    tools: list[dict] | None = None,
    max_tokens: int = 1500,
) -> dict:
    if anthropic_client.is_configured():
        return anthropic_client.call_claude(messages, system=system, tools=tools, max_tokens=max_tokens)
    if gemini_client.is_configured():
        return gemini_client.call_gemini(messages, system=system, tools=tools, max_tokens=max_tokens)
    return {}
