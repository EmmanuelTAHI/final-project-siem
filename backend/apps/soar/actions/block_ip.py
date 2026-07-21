"""
Action SOAR : blocage d'une IP (via webhook firewall ou API externe).
En production : appeler l'API du firewall/NGFW ou pousser une règle iptables.
"""
import logging

import httpx

logger = logging.getLogger(__name__)


def execute(params: dict, alert) -> dict:
    """
    params: {
        firewall_api_url: "https://...",
        api_key: "...",
        block_duration_hours: 24,
        target_ips: [...]  # si vide, utilise source_ips de l'alerte
    }
    """
    from apps.logs.models import NormalizedLog

    firewall_url = params.get("firewall_api_url", "")
    target_ips = params.get("target_ips", [])

    if not target_ips:
        target_ips = list(
            alert.source_logs.exclude(source_ip__isnull=True)
            .values_list("source_ip", flat=True)
            .distinct()
        )

    if not target_ips:
        return {"status": "skipped", "reason": "no_ips_found"}

    if getattr(alert.organization, "is_demo", False):
        # Tenant de démonstration publique : simule le blocage plutôt que
        # d'appeler un vrai firewall/NGFW pour une action déclenchée par un
        # spectateur anonyme.
        logger.info("[DEMO] Blocage IP simulé pour %s (alerte %s)", target_ips, alert.id)
        return {"status": "simulated", "blocked_ips": target_ips}

    blocked = []
    failed = []

    for ip in target_ips:
        if ip in ("127.0.0.1", "::1", "0.0.0.0"):
            continue
        if firewall_url:
            try:
                with httpx.Client(timeout=10.0) as client:
                    resp = client.post(
                        firewall_url,
                        json={"ip": ip, "action": "block", "duration_hours": params.get("block_duration_hours", 24)},
                        headers={"Authorization": f"Bearer {params.get('api_key', '')}"},
                    )
                    resp.raise_for_status()
                    blocked.append(ip)
            except httpx.HTTPError as exc:
                failed.append({"ip": ip, "error": str(exc)})
        else:
            logger.warning("SOAR block_ip: aucune firewall_api_url configurée. IP ciblée: %s", ip)
            blocked.append(ip)

    logger.info("SOAR block_ip: bloquées=%s, échouées=%s", blocked, failed)
    return {"status": "success" if not failed else "partial", "blocked_ips": blocked, "failed": failed}
