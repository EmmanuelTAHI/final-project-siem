from django.urls import include, path
from rest_framework.routers import DefaultRouter
from .views import CTIStatsView, EnrichedLogViewSet, ThreatIndicatorViewSet

router = DefaultRouter()
router.register("indicators", ThreatIndicatorViewSet, basename="indicator")
router.register("enriched-logs", EnrichedLogViewSet, basename="enriched-log")

urlpatterns = [
    path("", include(router.urls)),
    path("stats/", CTIStatsView.as_view(), name="cti-stats"),
]
