from django.urls import include, path
from rest_framework.routers import DefaultRouter

from .views import LogStatsView, NormalizedLogViewSet, RawLogViewSet

router = DefaultRouter()
router.register(r"raw", RawLogViewSet, basename="raw-logs")
router.register(r"normalized", NormalizedLogViewSet, basename="normalized-logs")

urlpatterns = [
    path("", include(router.urls)),
    path("stats/", LogStatsView.as_view(), name="log-stats"),
]
