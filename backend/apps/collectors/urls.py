from django.urls import include, path
from rest_framework.routers import DefaultRouter

from .views import CollectionJobViewSet, ConnectorConfigViewSet

router = DefaultRouter()
router.register(r"connectors", ConnectorConfigViewSet, basename="connectors")
router.register(r"jobs", CollectionJobViewSet, basename="collection-jobs")

urlpatterns = [
    path("", include(router.urls)),
]
