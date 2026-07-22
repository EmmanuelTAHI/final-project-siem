"""
Routage principal du projet Argus.
PFE Argus — TAHI Ezan Franck Emmanuel — 2025-2026
"""
from django.contrib import admin
from django.http import JsonResponse
from django.urls import include, path

from apps.collectors.ingest_views import AgentLogIngestView


def health_check(request):
    from django.core.cache import cache
    redis_ok = False
    try:
        cache.set("_health", "1", timeout=5)
        redis_ok = cache.get("_health") == "1"
    except Exception:
        pass
    return JsonResponse({"status": "ok", "redis": redis_ok})


urlpatterns = [
    path("api/health/", health_check),
    path("admin/", admin.site.urls),
    path("api/auth/", include("apps.authentication.urls")),
    path("api/users/", include("apps.users.urls")),
    path("api/collectors/", include("apps.collectors.urls")),
    path("api/logs/", include("apps.logs.urls")),
    path("api/correlation/", include("apps.correlation.urls")),
    path("api/alerts/", include("apps.alerts.urls")),
    path("api/ml/", include("apps.ml.urls")),
    path("api/dashboard/", include("apps.dashboard.urls")),
    # Nouvelles fonctionnalités avancées
    path("api/threat-intel/", include("apps.threat_intel.urls")),
    path("api/soar/", include("apps.soar.urls")),
    path("api/reports/", include("apps.reports.urls")),
    path("api/hunting/", include("apps.hunting.urls")),
    path("api/tickets/", include("apps.tickets.urls")),
    path("api/copilot/", include("apps.copilot.urls")),
    # Ingestion agents — auth par token bearer dédiée, PAS de session JWT humaine.
    path("api/ingest/agent/logs/", AgentLogIngestView.as_view(), name="agent-log-ingest"),
    # Vue cross-org réservée au staff plateforme (super-admin) — IsPlatformStaff.
    path("api/platform/", include("apps.organizations.urls")),
]
