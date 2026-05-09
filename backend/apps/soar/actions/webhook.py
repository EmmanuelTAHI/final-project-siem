"""Action SOAR : appel webhook externe (Slack, Teams, PagerDuty...)."""
import logging

import httpx

logger = logging.getLogger(__name__)


def execute(params: dict, alert) -> dict:
    """
    params: {url: "https://...", method: "POST", payload_template: {...}, headers: {...}}
    """
    url = params.get("url", "")
    if not url:
        return {"status": "skipped", "reason": "no_url"}

    method = params.get("method", "POST").upper()
    headers = params.get("headers", {"Content-Type": "application/json"})

    payload = {
        "alert_id": str(alert.id),
        "title": alert.title,
        "severity": alert.severity,
        "status": alert.status,
        "created_at": alert.created_at.isoformat(),
        "description": alert.description,
    }
    payload.update(params.get("extra_payload", {}))

    try:
        with httpx.Client(timeout=10.0) as client:
            resp = client.request(method, url, json=payload, headers=headers)
            resp.raise_for_status()
            logger.info("Webhook %s appelé pour alerte %s — HTTP %s", url, alert.id, resp.status_code)
            return {"status": "success", "http_status": resp.status_code, "url": url}
    except httpx.HTTPError as exc:
        logger.error("Webhook failed (%s): %s", url, exc)
        return {"status": "failed", "error": str(exc)}
