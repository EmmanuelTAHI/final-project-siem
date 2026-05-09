from django.urls import include, path
from rest_framework.routers import DefaultRouter
from .views import HuntingQueryViewSet, HuntView

router = DefaultRouter()
router.register("queries", HuntingQueryViewSet, basename="hunting-query")

urlpatterns = [
    path("", include(router.urls)),
    path("run/", HuntView.as_view(), name="hunt-run"),
]
