from django.urls import include, path
from rest_framework.routers import DefaultRouter

from .views import CorrelationRuleViewSet

router = DefaultRouter()
router.register(r"rules", CorrelationRuleViewSet, basename="correlation-rules")

urlpatterns = [
    path("", include(router.urls)),
]
