"""
Vues pour les connecteurs et jobs de collecte.
"""
import logging

from django_filters.rest_framework import DjangoFilterBackend
from rest_framework import filters, status
from rest_framework.decorators import action
from rest_framework.viewsets import ModelViewSet, ReadOnlyModelViewSet

from utils.permissions import IsAdmin, IsAnalyst
from utils.response import created_response, error_response, no_content_response, success_response

from .models import CollectionJob, ConnectorConfig
from .serializers import (
    CollectionJobSerializer,
    ConnectorConfigCreateSerializer,
    ConnectorConfigSerializer,
)

logger = logging.getLogger(__name__)


class ConnectorConfigViewSet(ModelViewSet):
    """
    CRUD complet pour les connecteurs de collecte.
    GET    /api/collectors/connectors/
    POST   /api/collectors/connectors/
    GET    /api/collectors/connectors/{id}/
    PUT    /api/collectors/connectors/{id}/
    DELETE /api/collectors/connectors/{id}/
    POST   /api/collectors/connectors/{id}/test/
    POST   /api/collectors/connectors/{id}/collect/
    """

    queryset = ConnectorConfig.objects.all().order_by("-created_at")
    filter_backends = [DjangoFilterBackend, filters.SearchFilter]
    filterset_fields = ["source_type", "is_active"]
    search_fields = ["name"]

    def get_serializer_class(self):
        if self.action in ("create", "update", "partial_update"):
            return ConnectorConfigCreateSerializer
        return ConnectorConfigSerializer

    def get_permissions(self):
        if self.action in ("create", "destroy"):
            return [IsAdmin()]
        if self.action in ("update", "partial_update"):
            return [IsAdmin()]
        return [IsAnalyst()]

    def list(self, request, *args, **kwargs):
        queryset = self.filter_queryset(self.get_queryset())
        page = self.paginate_queryset(queryset)
        if page is not None:
            serializer = ConnectorConfigSerializer(page, many=True)
            return self.get_paginated_response(serializer.data)
        serializer = ConnectorConfigSerializer(queryset, many=True)
        return success_response(data=serializer.data, message="Liste des connecteurs.")

    def create(self, request, *args, **kwargs):
        serializer = ConnectorConfigCreateSerializer(data=request.data)
        if not serializer.is_valid():
            return error_response(message="Données invalides.", errors=serializer.errors)
        connector = serializer.save(created_by=request.user)
        from apps.users.models import AuditTrail
        AuditTrail.log(
            action="connector_create",
            user=request.user,
            target_model="ConnectorConfig",
            target_id=connector.id,
        )
        return created_response(
            data=ConnectorConfigSerializer(connector).data,
            message="Connecteur créé avec succès.",
        )

    def retrieve(self, request, *args, **kwargs):
        connector = self.get_object()
        return success_response(data=ConnectorConfigSerializer(connector).data)

    def update(self, request, *args, **kwargs):
        partial = kwargs.pop("partial", False)
        connector = self.get_object()
        serializer = ConnectorConfigCreateSerializer(connector, data=request.data, partial=partial)
        if not serializer.is_valid():
            return error_response(message="Données invalides.", errors=serializer.errors)
        connector = serializer.save()
        from apps.users.models import AuditTrail
        AuditTrail.log(action="connector_update", user=request.user, target_model="ConnectorConfig", target_id=connector.id)
        return success_response(data=ConnectorConfigSerializer(connector).data, message="Connecteur mis à jour.")

    def destroy(self, request, *args, **kwargs):
        connector = self.get_object()
        from apps.users.models import AuditTrail
        AuditTrail.log(action="connector_delete", user=request.user, target_model="ConnectorConfig", target_id=connector.id)
        connector.delete()
        return no_content_response("Connecteur supprimé.")

    @action(detail=True, methods=["post"], permission_classes=[IsAnalyst])
    def test(self, request, pk=None):
        """
        POST /api/collectors/connectors/{id}/test/
        Teste la connexion à la source et retourne la latence.
        """
        connector = self.get_object()
        from apps.collectors.sources.microsoft_collector import MicrosoftCollector
        from apps.collectors.sources.google_collector import GoogleCollector
        from apps.collectors.sources.wazuh_collector import WazuhCollector
        from apps.collectors.sources.syslog_collector import SyslogCollector

        collector_map = {
            "microsoft365": MicrosoftCollector,
            "google_workspace": GoogleCollector,
            "wazuh": WazuhCollector,
            "syslog": SyslogCollector,
        }
        collector_class = collector_map.get(connector.source_type)
        if not collector_class:
            return error_response(
                message=f"Test non disponible pour le type '{connector.source_type}'.",
                http_status=status.HTTP_400_BAD_REQUEST,
            )
        try:
            result = collector_class(connector).test_connection()
            return success_response(data=result, message="Test de connexion effectué.")
        except Exception as exc:
            return error_response(
                message=f"Erreur lors du test : {str(exc)}",
                http_status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )

    @action(detail=True, methods=["post"], permission_classes=[IsAnalyst], url_path="collect")
    def collect(self, request, pk=None):
        """
        POST /api/collectors/connectors/{id}/collect/
        Déclenche une collecte manuelle immédiate via Celery.
        """
        connector = self.get_object()
        from apps.collectors.tasks import manual_collect
        task = manual_collect.delay(str(connector.id))
        return success_response(
            data={"job_id": task.id, "status": "pending"},
            message="Collecte manuelle lancée. Vérifiez le statut via /api/collectors/jobs/.",
            http_status=status.HTTP_202_ACCEPTED,
        )


class CollectionJobViewSet(ReadOnlyModelViewSet):
    """
    Historique des jobs de collecte — lecture seule.
    GET /api/collectors/jobs/
    GET /api/collectors/jobs/{id}/
    """

    queryset = CollectionJob.objects.select_related("connector").all()
    serializer_class = CollectionJobSerializer
    permission_classes = [IsAnalyst]
    filter_backends = [DjangoFilterBackend, filters.OrderingFilter]
    filterset_fields = ["connector", "status"]
    ordering_fields = ["started_at", "finished_at", "logs_collected_count"]
    ordering = ["-started_at"]

    def list(self, request, *args, **kwargs):
        # Filtre par dates si fourni
        queryset = self.filter_queryset(self.get_queryset())
        date_from = request.query_params.get("date_from")
        date_to = request.query_params.get("date_to")
        if date_from:
            queryset = queryset.filter(started_at__gte=date_from)
        if date_to:
            queryset = queryset.filter(started_at__lte=date_to)

        page = self.paginate_queryset(queryset)
        if page is not None:
            serializer = self.get_serializer(page, many=True)
            return self.get_paginated_response(serializer.data)
        serializer = self.get_serializer(queryset, many=True)
        return success_response(data=serializer.data, message="Historique des jobs de collecte.")

    def retrieve(self, request, *args, **kwargs):
        job = self.get_object()
        return success_response(data=self.get_serializer(job).data)
