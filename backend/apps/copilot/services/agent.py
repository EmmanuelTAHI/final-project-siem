"""
Boucle agentique du SOC Copilot : Claude peut demander l'exécution d'outils
(query_logs, query_alerts...) plusieurs fois avant de donner sa réponse
finale. Chaque appel d'outil est exécuté côté serveur, scopé à
`organization_id` — le modèle ne reçoit jamais d'accès direct aux données,
seulement ce que les outils lui renvoient.
"""
import json
import logging

from .llm_client import call_llm, is_configured
from .tools import TOOL_SCHEMAS, execute_tool

logger = logging.getLogger(__name__)

MAX_TOOL_ROUNDS = 4

SYSTEM_PROMPT = (
    "Tu es le SOC Copilot d'Argus, un assistant de sécurité intégré à un SIEM. "
    "Tu réponds en français, de façon concise et actionnable, aux questions d'un "
    "analyste de sécurité sur les logs, alertes et vulnérabilités de SON organisation. "
    "Utilise TOUJOURS les outils à ta disposition pour vérifier les données réelles "
    "avant de répondre — ne devine jamais un chiffre ou un fait que tu peux vérifier. "
    "Si les outils ne renvoient aucun résultat pertinent, dis-le clairement plutôt "
    "que d'inventer. Termine par une recommandation concrète quand c'est pertinent."
)


def ask(question: str, organization_id, history: list[dict] | None = None) -> dict:
    """
    Pose une question au SOC Copilot. Retourne
    {"answer": str, "tool_calls": [...], "configured": bool}.
    """
    if not is_configured():
        return {
            "answer": (
                "Le SOC Copilot n'est pas configuré sur cette instance "
                "(ni ANTHROPIC_API_KEY, ni GOOGLE_AI_API_KEY). Ajoutez l'une des deux "
                "clés dans le fichier .env pour activer cette fonctionnalité."
            ),
            "tool_calls": [],
            "configured": False,
        }

    messages = list(history or [])
    messages.append({"role": "user", "content": question})

    tool_calls_log = []

    for _round in range(MAX_TOOL_ROUNDS):
        result = call_llm(messages, system=SYSTEM_PROMPT, tools=TOOL_SCHEMAS)
        content_blocks = result.get("content", [])
        stop_reason = result.get("stop_reason")

        if not content_blocks:
            return {
                "answer": "Le SOC Copilot n'a pas pu générer de réponse (service IA indisponible).",
                "tool_calls": tool_calls_log,
                "configured": True,
            }

        if stop_reason != "tool_use":
            text = "".join(b.get("text", "") for b in content_blocks if b.get("type") == "text")
            return {"answer": text.strip(), "tool_calls": tool_calls_log, "configured": True}

        # Le modèle demande à utiliser un ou plusieurs outils.
        messages.append({"role": "assistant", "content": content_blocks})
        tool_results = []
        for block in content_blocks:
            if block.get("type") != "tool_use":
                continue
            tool_name = block.get("name")
            tool_input = block.get("input", {})
            output = execute_tool(tool_name, tool_input, organization_id)
            tool_calls_log.append({"tool": tool_name, "input": tool_input, "output_summary": _summarize(output)})
            tool_results.append({
                "type": "tool_result",
                "tool_use_id": block.get("id"),
                "content": json.dumps(output, default=str)[:8000],
            })
        messages.append({"role": "user", "content": tool_results})

    return {
        "answer": "Le SOC Copilot a atteint la limite d'itérations d'outils sans conclure — reformulez votre question.",
        "tool_calls": tool_calls_log,
        "configured": True,
    }


def _summarize(output: dict) -> str:
    if "total_matching" in output:
        return f"{output['total_matching']} résultat(s) trouvé(s)"
    if "indicators" in output:
        return f"{len(output['indicators'])} indicateur(s) CTI trouvé(s)"
    return "ok"


def summarize_alert(alert) -> dict:
    """
    Génère un résumé d'incident + actions recommandées pour une alerte, via
    l'IA. Retourne {"summary": str, "recommended_actions": [str, ...]} — ou un
    message d'indisponibilité si l'IA n'est pas configurée.
    """
    if not is_configured():
        return {
            "summary": "SOC Copilot non configuré (ni ANTHROPIC_API_KEY, ni GOOGLE_AI_API_KEY).",
            "recommended_actions": [],
        }

    source_logs = list(alert.source_logs.all()[:10])
    logs_context = "\n".join(
        f"- {log.event_time}: {log.action} ({log.outcome}) IP={log.source_ip} user={log.user_email} pays={log.geo_country}"
        for log in source_logs
    ) or "Aucun log source détaillé disponible."

    prompt = (
        f"Alerte SOC :\n"
        f"Titre : {alert.title}\n"
        f"Sévérité : {alert.severity}\n"
        f"Description : {alert.description}\n\n"
        f"Logs sources (jusqu'à 10) :\n{logs_context}\n\n"
        "Réponds STRICTEMENT en JSON valide avec ce format exact, sans texte "
        'autour : {"summary": "résumé en 2-3 phrases pour un analyste pressé", '
        '"recommended_actions": ["action 1", "action 2", "action 3"]}'
    )

    result = call_llm(
        [{"role": "user", "content": prompt}],
        system="Tu es un analyste SOC senior. Tu réponds uniquement en JSON valide, en français.",
        max_tokens=800,
    )
    content_blocks = result.get("content", [])
    text = "".join(b.get("text", "") for b in content_blocks if b.get("type") == "text")

    try:
        start = text.index("{")
        end = text.rindex("}") + 1
        parsed = json.loads(text[start:end])
        return {
            "summary": parsed.get("summary", ""),
            "recommended_actions": parsed.get("recommended_actions", []),
        }
    except (ValueError, json.JSONDecodeError):
        logger.warning("Réponse IA non parsable pour l'alerte %s", alert.id)
        return {"summary": text.strip() or "Réponse IA non exploitable.", "recommended_actions": []}
