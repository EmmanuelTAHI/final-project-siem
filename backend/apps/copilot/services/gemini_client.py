"""
Client Google Gemini (AI Studio) via httpx — repli gratuit quand
ANTHROPIC_API_KEY n'est pas configurée. Traduit dans les deux sens le format
de conversation "à la Anthropic" (content blocks text/tool_use/tool_result)
utilisé par agent.py, pour que ce dernier reste inchangé quel que soit le
fournisseur choisi.
"""
import json
import logging
import uuid

import httpx
from django.conf import settings

logger = logging.getLogger(__name__)

GEMINI_API_URL = "https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent"


def is_configured() -> bool:
    return bool(getattr(settings, "GOOGLE_AI_API_KEY", ""))


def _to_gemini_contents(messages: list[dict]) -> list[dict]:
    """Traduit les messages (format blocs Anthropic) en `contents` Gemini."""
    contents = []
    tool_id_to_name: dict[str, str] = {}

    for msg in messages:
        role = msg["role"]
        content = msg["content"]

        if isinstance(content, str):
            contents.append({"role": "user" if role == "user" else "model", "parts": [{"text": content}]})
            continue

        parts = []
        has_function_response = False
        for block in content:
            btype = block.get("type")
            if btype == "text":
                parts.append({"text": block.get("text", "")})
            elif btype == "tool_use":
                tool_id_to_name[block.get("id")] = block.get("name")
                parts.append({"functionCall": {"name": block.get("name"), "args": block.get("input", {})}})
            elif btype == "tool_result":
                has_function_response = True
                name = tool_id_to_name.get(block.get("tool_use_id"), "unknown_tool")
                raw = block.get("content")
                try:
                    response_obj = json.loads(raw) if isinstance(raw, str) else raw
                except (TypeError, ValueError):
                    response_obj = {"result": raw}
                if not isinstance(response_obj, dict):
                    response_obj = {"result": response_obj}
                parts.append({"functionResponse": {"name": name, "response": response_obj}})

        gemini_role = "function" if has_function_response else ("user" if role == "user" else "model")
        contents.append({"role": gemini_role, "parts": parts})

    return contents


def _tools_to_gemini(tools: list[dict]) -> list[dict]:
    declarations = [
        {"name": t["name"], "description": t.get("description", ""), "parameters": t.get("input_schema", {"type": "object", "properties": {}})}
        for t in tools
    ]
    return [{"functionDeclarations": declarations}]


def call_gemini(
    messages: list[dict],
    system: str = "",
    tools: list[dict] | None = None,
    max_tokens: int = 1500,
) -> dict:
    """
    Appelle l'API Gemini generateContent et retourne le résultat dans le
    MÊME format que anthropic_client.call_claude :
    {"content": [{"type": "text", "text": ...} | {"type": "tool_use", "id", "name", "input"}],
     "stop_reason": "tool_use" | "end_turn"}
    ou {} si la clé n'est pas configurée / en cas d'erreur réseau.
    """
    api_key = getattr(settings, "GOOGLE_AI_API_KEY", "")
    if not api_key:
        logger.debug("GOOGLE_AI_API_KEY non configurée")
        return {}

    model = getattr(settings, "GOOGLE_AI_MODEL", "gemini-2.0-flash")
    payload: dict = {
        "contents": _to_gemini_contents(messages),
        "generationConfig": {"maxOutputTokens": max_tokens},
    }
    if system:
        payload["systemInstruction"] = {"parts": [{"text": system}]}
    if tools:
        payload["tools"] = _tools_to_gemini(tools)

    try:
        with httpx.Client(timeout=45.0) as client:
            resp = client.post(
                GEMINI_API_URL.format(model=model),
                params={"key": api_key},
                json=payload,
            )
            resp.raise_for_status()
            data = resp.json()
    except httpx.HTTPError as exc:
        logger.warning("Appel Gemini échoué : %s", exc)
        return {}

    candidates = data.get("candidates") or []
    if not candidates:
        return {"content": [], "stop_reason": "end_turn"}

    gemini_parts = candidates[0].get("content", {}).get("parts", [])
    content_blocks = []
    for part in gemini_parts:
        if "text" in part:
            content_blocks.append({"type": "text", "text": part["text"]})
        elif "functionCall" in part:
            fc = part["functionCall"]
            content_blocks.append({
                "type": "tool_use",
                "id": f"call_{uuid.uuid4().hex[:12]}",
                "name": fc.get("name"),
                "input": fc.get("args", {}),
            })

    stop_reason = "tool_use" if any(b["type"] == "tool_use" for b in content_blocks) else "end_turn"
    return {"content": content_blocks, "stop_reason": stop_reason}
