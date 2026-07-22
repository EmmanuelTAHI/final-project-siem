from django.urls import include, path
from rest_framework.routers import DefaultRouter

from .views import CorrelationRuleViewSet, MitreAttackCoverageView, MitreAttackReferenceView

router = DefaultRouter()
router.register(r"rules", CorrelationRuleViewSet, basename="correlation-rules")

urlpatterns = [
    path("", include(router.urls)),
    path("mitre-attack/", MitreAttackReferenceView.as_view(), name="mitre-attack-reference"),
    path("mitre-attack/coverage/", MitreAttackCoverageView.as_view(), name="mitre-attack-coverage"),
]
