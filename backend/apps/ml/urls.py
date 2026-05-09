from django.urls import include, path
from rest_framework.routers import DefaultRouter

from .views import MLModelViewSet, PredictionViewSet, TrainStatusView, TrainView

router = DefaultRouter()
router.register(r"models", MLModelViewSet, basename="ml-models")
router.register(r"predictions", PredictionViewSet, basename="ml-predictions")

urlpatterns = [
    path("", include(router.urls)),
    path("train/", TrainView.as_view(), name="ml-train"),
    path("train/<str:task_id>/status/", TrainStatusView.as_view(), name="ml-train-status"),
]
