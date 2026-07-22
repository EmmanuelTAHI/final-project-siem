from django.urls import include, path
from rest_framework.routers import DefaultRouter

from .views import AlertSummarizeView, CopilotAskView, CopilotConversationViewSet

router = DefaultRouter()
router.register("conversations", CopilotConversationViewSet, basename="copilot-conversation")

urlpatterns = [
    path("", include(router.urls)),
    path("ask/", CopilotAskView.as_view(), name="copilot-ask"),
    path("alerts/<uuid:alert_id>/summarize/", AlertSummarizeView.as_view(), name="copilot-alert-summarize"),
]
