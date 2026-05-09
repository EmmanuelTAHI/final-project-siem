"""
Vues pour le module Machine Learning.
"""
import logging

from celery.result import AsyncResult
from django_filters.rest_framework import DjangoFilterBackend
from rest_framework import filters, status
from rest_framework.views import APIView
from rest_framework.viewsets import ReadOnlyModelViewSet

from utils.permissions import IsAdmin, IsAnalyst
from utils.response import error_response, success_response

from .models import MLModel, Prediction
from .serializers import MLModelSerializer, PredictionSerializer, TrainRequestSerializer

logger = logging.getLogger(__name__)


class MLModelViewSet(ReadOnlyModelViewSet):
    """
    GET /api/ml/models/
    GET /api/ml/models/{id}/
    """

    queryset = MLModel.objects.all()
    serializer_class = MLModelSerializer
    permission_classes = [IsAnalyst]

    def list(self, request, *args, **kwargs):
        queryset = self.filter_queryset(self.get_queryset())
        page = self.paginate_queryset(queryset)
        if page is not None:
            serializer = self.get_serializer(page, many=True)
            return self.get_paginated_response(serializer.data)
        serializer = self.get_serializer(queryset, many=True)
        return success_response(data=serializer.data, message="Liste des modèles ML.")

    def retrieve(self, request, *args, **kwargs):
        model = self.get_object()
        return success_response(data=self.get_serializer(model).data)


class TrainView(APIView):
    """
    POST /api/ml/train/
    Lance l'entraînement Isolation Forest en tâche Celery.
    """

    permission_classes = [IsAnalyst]

    def post(self, request):
        serializer = TrainRequestSerializer(data=request.data)
        if not serializer.is_valid():
            return error_response(message="Paramètres invalides.", errors=serializer.errors)

        days_of_data = serializer.validated_data["days_of_data"]
        contamination = serializer.validated_data["contamination"]

        from apps.ml.tasks import train_isolation_forest
        task = train_isolation_forest.delay(
            days_of_data=days_of_data,
            contamination=contamination,
        )

        logger.info(
            "Entraînement ML lancé — task_id=%s, days=%d, contamination=%.2f",
            task.id,
            days_of_data,
            contamination,
        )
        return success_response(
            data={
                "task_id": task.id,
                "status": "pending",
                "parameters": {
                    "days_of_data": days_of_data,
                    "contamination": contamination,
                },
            },
            message="Entraînement lancé. Suivez la progression via /api/ml/train/{task_id}/status/",
            http_status=status.HTTP_202_ACCEPTED,
        )


class TrainStatusView(APIView):
    """
    GET /api/ml/train/{task_id}/status/
    Suit la progression d'une tâche d'entraînement Celery.
    """

    permission_classes = [IsAnalyst]

    def get(self, request, task_id):
        try:
            result = AsyncResult(task_id)
            state = result.state
            data = {
                "task_id": task_id,
                "status": state,
            }

            if state == "SUCCESS":
                data["result"] = result.result
            elif state == "FAILURE":
                data["error"] = str(result.result)
            elif state == "PENDING":
                data["message"] = "Tâche en attente d'exécution."
            elif state == "STARTED":
                data["message"] = "Entraînement en cours..."

            return success_response(data=data, message=f"Statut de la tâche : {state}")
        except Exception as exc:
            return error_response(
                message=f"Impossible de récupérer le statut de la tâche : {str(exc)}",
                http_status=status.HTTP_400_BAD_REQUEST,
            )


class PredictionViewSet(ReadOnlyModelViewSet):
    """
    GET /api/ml/predictions/
    GET /api/ml/predictions/{id}/
    """

    queryset = Prediction.objects.select_related("log", "model").all()
    serializer_class = PredictionSerializer
    permission_classes = [IsAnalyst]
    filter_backends = [DjangoFilterBackend, filters.OrderingFilter]
    filterset_fields = ["is_anomaly", "model"]
    ordering_fields = ["predicted_at", "anomaly_score"]
    ordering = ["-predicted_at"]

    def get_queryset(self):
        qs = super().get_queryset()
        date_from = self.request.query_params.get("date_from")
        date_to = self.request.query_params.get("date_to")
        log_id = self.request.query_params.get("log")
        if date_from:
            qs = qs.filter(predicted_at__gte=date_from)
        if date_to:
            qs = qs.filter(predicted_at__lte=date_to)
        if log_id:
            qs = qs.filter(log_id=log_id)
        return qs

    def list(self, request, *args, **kwargs):
        queryset = self.filter_queryset(self.get_queryset())
        page = self.paginate_queryset(queryset)
        if page is not None:
            serializer = self.get_serializer(page, many=True)
            return self.get_paginated_response(serializer.data)
        serializer = self.get_serializer(queryset, many=True)
        return success_response(data=serializer.data, message="Liste des prédictions ML.")

    def retrieve(self, request, *args, **kwargs):
        prediction = self.get_object()
        return success_response(data=self.get_serializer(prediction).data)
