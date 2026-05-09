from django.urls import include, path
from rest_framework.routers import DefaultRouter

from .views import AlertViewSet

router = DefaultRouter()
router.register(r"", AlertViewSet, basename="alerts")

urlpatterns = [
    path("", include(router.urls)),
]
