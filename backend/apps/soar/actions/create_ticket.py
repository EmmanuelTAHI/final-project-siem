"""Action SOAR : création de ticket dans un système ITSM (Jira, ServiceNow...)."""
import logging

import httpx

logger = logging.getLogger(__name__)


def execute(params: dict, alert) -> dict:
    """
    params: {
        system: "jira" | "servicenow" | "generic",
        api_url: "https://...",
        api_key: "...",
        project_key: "SOC",
        priority_map: {critical: "Highest", high: "High", ...}
    }
    """
    api_url = params.get("api_url", "")
    if not api_url:
        return {"status": "skipped", "reason": "no_api_url"}

    priority_map = params.get("priority_map", {
        "critical": "Highest", "high": "High", "medium": "Medium", "low": "Low"
    })

    payload = {
        "title": f"[Log+] {alert.title}",
        "description": alert.description,
        "priority": priority_map.get(alert.severity, "Medium"),
        "labels": ["logplus", alert.severity, "auto-generated"],
        "alert_id": str(alert.id),
    }

    system = params.get("system", "generic")
    if system == "jira":
        payload = {
            "fields": {
                "project": {"key": params.get("project_key", "SOC")},
                "summary": payload["title"],
                "description": payload["description"],
                "issuetype": {"name": "Bug"},
                "priority": {"name": payload["priority"]},
                "labels": payload["labels"],
            }
        }

    try:
        with httpx.Client(timeout=15.0) as client:
            resp = client.post(
                api_url,
                json=payload,
                headers={
                    "Authorization": f"Bearer {params.get('api_key', '')}",
                    "Content-Type": "application/json",
                },
            )
            resp.raise_for_status()
            ticket_id = resp.json().get("id") or resp.json().get("key", "unknown")
            logger.info("Ticket créé: %s pour alerte %s", ticket_id, alert.id)
            return {"status": "success", "ticket_id": ticket_id}
    except httpx.HTTPError as exc:
        logger.error("Ticket creation failed: %s", exc)
        return {"status": "failed", "error": str(exc)}
