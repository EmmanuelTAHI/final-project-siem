from django.urls import include, path
from rest_framework.routers import DefaultRouter
from .views import PlaybookExecutionViewSet, PlaybookViewSet, SOARStatsView

router = DefaultRouter()
router.register("playbooks", PlaybookViewSet, basename="playbook")
router.register("executions", PlaybookExecutionViewSet, basename="execution")

urlpatterns = [
    path("", include(router.urls)),
    path("stats/", SOARStatsView.as_view(), name="soar-stats"),
]
