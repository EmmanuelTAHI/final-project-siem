"""
Action SOAR : blocage d'une IP.

Deux couches, appliquées ensemble :
1. Blocage LOCAL réel : une ligne `apps.soar.models.BlockedIP` est toujours
   créée — `utils.blocklist_middleware.BlockedIPMiddleware` la fait respecter
   sur CHAQUE requête API dès le prochain appel (403 immédiat), sans
   dépendre d'une intégration externe. Ce n'est plus un simple log qui
   prétend avoir bloqué : l'IP est effectivement rejetée par la plateforme.
2. Blocage externe optionnel : si `firewall_api_url` est fourni, appel en
   plus vers un vrai firewall/NGFW/CrowdSec pour bloquer au niveau réseau
   (utile si l'IP attaque aussi d'autres services que ce SIEM).
"""
import logging

import httpx

logger = logging.getLogger(__name__)


def execute(params: dict, alert) -> dict:
    """
    params: {
        firewall_api_url: "https://...",  # optionnel
        api_key: "...",
        block_duration_hours: 24,
        target_ips: [...]  # si vide, utilise source_ips de l'alerte
    }
    """
    from django.utils import timezone

    from apps.soar.models import BlockedIP

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
        # d'appliquer un vrai blocage pour une action déclenchée par un
        # spectateur anonyme.
        logger.info("[DEMO] Blocage IP simulé pour %s (alerte %s)", target_ips, alert.id)
        return {"status": "simulated", "blocked_ips": target_ips}

    duration_hours = params.get("block_duration_hours", 24)
    expires_at = (
        timezone.now() + timezone.timedelta(hours=duration_hours) if duration_hours else None
    )

    blocked = []
    failed = []

    for ip in target_ips:
        if ip in ("127.0.0.1", "::1", "0.0.0.0"):
            continue

        # Couche 1 — toujours appliquée, réellement effective sur la plateforme.
        BlockedIP.objects.update_or_create(
            organization=alert.organization,
            ip_address=ip,
            defaults={
                "reason": f"Playbook SOAR — alerte : {alert.title[:200]}",
                "source": "soar_playbook",
                "is_active": True,
                "expires_at": expires_at,
            },
        )

        # Couche 2 — optionnelle, firewall/NGFW externe.
        if firewall_url:
            try:
                with httpx.Client(timeout=10.0) as client:
                    resp = client.post(
                        firewall_url,
                        json={"ip": ip, "action": "block", "duration_hours": duration_hours},
                        headers={"Authorization": f"Bearer {params.get('api_key', '')}"},
                    )
                    resp.raise_for_status()
            except httpx.HTTPError as exc:
                failed.append({"ip": ip, "error": str(exc)})
                continue

        blocked.append(ip)

    logger.info("SOAR block_ip: bloquées localement=%s, échecs firewall externe=%s", blocked, failed)
    return {"status": "success" if not failed else "partial", "blocked_ips": blocked, "failed": failed}
