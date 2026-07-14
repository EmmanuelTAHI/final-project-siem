from django.urls import include, path
from rest_framework.routers import DefaultRouter

from .views import PlatformOrganizationViewSet

router = DefaultRouter()
router.register(r"organizations", PlatformOrganizationViewSet, basename="platform-organizations")

urlpatterns = [
    path("", include(router.urls)),
]
