"""
Application locale des blocages IP décidés par le SOAR (apps.soar.BlockedIP).

Contrairement à l'action SOAR `block_ip` historique (qui ne fait qu'appeler,
en option, un firewall/NGFW externe fourni en paramètre), ce middleware rend
le blocage RÉELLEMENT effectif au niveau de la plateforme elle-même : une IP
bloquée reçoit un 403 sur CHAQUE requête API, sans dépendre d'une intégration
tierce. C'est la même logique de défense en profondeur que
`DemoSpectatorReadOnlyMiddleware` (middleware plutôt que permission DRF, pour
s'appliquer même à une vue future mal configurée).

Le résultat est mis en cache (Redis, TTL court) pour éviter une requête DB à
chaque appel API — un nouveau blocage met donc jusqu'à `CACHE_TTL` secondes à
prendre effet, ce qui reste largement suffisant pour une réponse automatisée
(le blocage a de toute façon déjà mis plusieurs secondes à être décidé par le
moteur de corrélation + le playbook SOAR).
"""
from django.core.cache import cache
from django.http import JsonResponse

CACHE_TTL = 20
CACHE_KEY_PREFIX = "blocked_ip:"


def get_client_ip(request) -> str:
    """Même logique que apps.collectors.ingest_views._get_client_ip — nginx
    pose toujours X-Forwarded-For, REMOTE_ADDR est l'IP interne du conteneur."""
    x_forwarded = request.META.get("HTTP_X_FORWARDED_FOR")
    if x_forwarded:
        return x_forwarded.split(",")[0].strip()
    return request.META.get("REMOTE_ADDR", "")


def is_ip_blocked(ip: str) -> bool:
    if not ip:
        return False
    cache_key = f"{CACHE_KEY_PREFIX}{ip}"
    cached = cache.get(cache_key)
    if cached is not None:
        return cached

    from django.utils import timezone

    from apps.soar.models import BlockedIP

    blocked = BlockedIP.objects.filter(ip_address=ip, is_active=True).filter(
        expires_at__isnull=True
    ) | BlockedIP.objects.filter(ip_address=ip, is_active=True, expires_at__gt=timezone.now())
    result = blocked.exists()
    cache.set(cache_key, result, CACHE_TTL)
    return result


class BlockedIPMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        if request.path.startswith("/api/") and request.path != "/api/health/":
            ip = get_client_ip(request)
            if is_ip_blocked(ip):
                return JsonResponse(
                    {
                        "success": False,
                        "message": "Adresse IP bloquée par Argus SOAR suite à une activité malveillante détectée.",
                    },
                    status=403,
                )
        return self.get_response(request)
