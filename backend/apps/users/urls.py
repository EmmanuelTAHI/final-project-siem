from django.urls import include, path
from rest_framework.routers import DefaultRouter

from .views import AuditTrailViewSet, UserViewSet

router = DefaultRouter()
router.register(r"", UserViewSet, basename="users")
router.register(r"audit-trail", AuditTrailViewSet, basename="audit-trail")

urlpatterns = [
    path("", include(router.urls)),
]
