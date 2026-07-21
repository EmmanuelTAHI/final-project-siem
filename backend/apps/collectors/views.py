"""
Vues pour les connecteurs et jobs de collecte.
"""
import hashlib
import logging
import secrets

from django_filters.rest_framework import DjangoFilterBackend
from rest_framework import filters, status
from rest_framework.decorators import action
from rest_framework.viewsets import ModelViewSet, ReadOnlyModelViewSet

from utils.permissions import IsAdmin, IsAnalyst
from utils.response import created_response, error_response, no_content_response, success_response
from utils.tenant import OrganizationFilterBackend

from .models import AgentEnrollmentToken, CollectionJob, ConnectorConfig
from .serializers import (
    AgentEnrollmentTokenCreateSerializer,
    AgentEnrollmentTokenSerializer,
    CollectionJobSerializer,
    ConnectorConfigCreateSerializer,
    ConnectorConfigSerializer,
)

TOKEN_PREFIX = "argus_agt_"

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
    filter_backends = [OrganizationFilterBackend, DjangoFilterBackend, filters.SearchFilter]
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
        connector = serializer.save(created_by=request.user, organization=request.user.organization)
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
    filter_backends = [OrganizationFilterBackend, DjangoFilterBackend, filters.OrderingFilter]
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


class AgentEnrollmentTokenViewSet(ModelViewSet):
    """
    Gestion des tokens d'enrôlement d'agents (rsyslog/NXLog/Fluent Bit).
    GET    /api/collectors/enrollment-tokens/
    POST   /api/collectors/enrollment-tokens/            (IsAdmin — génère et renvoie le token EN CLAIR une seule fois)
    DELETE /api/collectors/enrollment-tokens/{id}/        (révocation)
    """

    queryset = AgentEnrollmentToken.objects.select_related("connector", "created_by").all()
    filter_backends = [OrganizationFilterBackend, DjangoFilterBackend, filters.OrderingFilter]
    filterset_fields = ["is_active"]
    ordering = ["-created_at"]
    http_method_names = ["get", "post", "delete", "head", "options"]

    def get_serializer_class(self):
        if self.action == "create":
            return AgentEnrollmentTokenCreateSerializer
        return AgentEnrollmentTokenSerializer

    def get_permissions(self):
        if self.action in ("create", "destroy"):
            return [IsAdmin()]
        return [IsAnalyst()]

    def list(self, request, *args, **kwargs):
        queryset = self.filter_queryset(self.get_queryset())
        page = self.paginate_queryset(queryset)
        if page is not None:
            serializer = AgentEnrollmentTokenSerializer(page, many=True)
            return self.get_paginated_response(serializer.data)
        serializer = AgentEnrollmentTokenSerializer(queryset, many=True)
        return success_response(data=serializer.data, message="Liste des tokens d'agent.")

    def create(self, request, *args, **kwargs):
        serializer = AgentEnrollmentTokenCreateSerializer(data=request.data)
        if not serializer.is_valid():
            return error_response(message="Données invalides.", errors=serializer.errors)

        raw_secret = secrets.token_urlsafe(32)
        prefix = raw_secret[:8]
        token_hash = hashlib.sha256(raw_secret.encode()).hexdigest()

        token = serializer.save(
            organization=request.user.organization,
            created_by=request.user,
            token_prefix=prefix,
            token_hash=token_hash,
        )

        from apps.users.models import AuditTrail
        AuditTrail.log(
            action="agent_token_create",
            user=request.user,
            target_model="AgentEnrollmentToken",
            target_id=token.id,
        )

        return created_response(
            data={
                **AgentEnrollmentTokenSerializer(token).data,
                # Renvoyé UNE seule fois — jamais stocké en clair, jamais récupérable ensuite.
                "token": f"{TOKEN_PREFIX}{raw_secret}",
            },
            message="Token généré. Copiez-le maintenant : il ne sera plus jamais affiché.",
        )

    def destroy(self, request, *args, **kwargs):
        token = self.get_object()
        token.is_active = False
        token.save(update_fields=["is_active"])
        from apps.users.models import AuditTrail
        AuditTrail.log(
            action="agent_token_revoke",
            user=request.user,
            target_model="AgentEnrollmentToken",
            target_id=token.id,
        )
        return no_content_response("Token révoqué.")
