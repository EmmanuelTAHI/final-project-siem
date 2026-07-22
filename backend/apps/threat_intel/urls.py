from django.urls import include, path
from rest_framework.routers import DefaultRouter
from .views import (
    AssetVulnerabilityViewSet,
    AssetViewSet,
    CTIStatsView,
    CVERecordViewSet,
    EnrichedLogViewSet,
    ThreatIndicatorViewSet,
)

router = DefaultRouter()
router.register("indicators", ThreatIndicatorViewSet, basename="indicator")
router.register("enriched-logs", EnrichedLogViewSet, basename="enriched-log")
router.register("cves", CVERecordViewSet, basename="cve")
router.register("assets", AssetViewSet, basename="asset")
router.register("asset-vulnerabilities", AssetVulnerabilityViewSet, basename="asset-vulnerability")

urlpatterns = [
    path("", include(router.urls)),
    path("stats/", CTIStatsView.as_view(), name="cti-stats"),
]
