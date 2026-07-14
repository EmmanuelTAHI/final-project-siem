"""
Vues plateforme (super-admin) — vue cross-org réservée au staff plateforme.

PlatformOrganizationViewSet est le SEUL ViewSet du code où
`allow_cross_org_for_platform_staff = True` doit apparaître : toute nouvelle
apparition de ce flag ailleurs doit être un signal d'alerte en revue de code
(voir utils.tenant.OrganizationFilterBackend et test_tenant_isolation.py).
"""
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.viewsets import ReadOnlyModelViewSet

from utils.permissions import IsPlatformStaff
from utils.response import success_response

from .models import Organization
from .serializers import OrganizationSerializer


class PlatformOrganizationViewSet(ReadOnlyModelViewSet):
    """
    GET /api/platform/organizations/
    GET /api/platform/organizations/{id}/
    GET /api/platform/organizations/{id}/stats/
    Réservé au staff plateforme (is_superuser).
    """

    queryset = Organization.objects.all().order_by("-created_at")
    serializer_class = OrganizationSerializer
    permission_classes = [IsPlatformStaff]
    allow_cross_org_for_platform_staff = True

    def list(self, request, *args, **kwargs):
        queryset = self.filter_queryset(self.get_queryset())
        serializer = self.get_serializer(queryset, many=True)
        return success_response(data=serializer.data, message="Liste des organisations.")

    def retrieve(self, request, *args, **kwargs):
        org = self.get_object()
        return success_response(data=self.get_serializer(org).data)

    @action(detail=True, methods=["get"])
    def stats(self, request, pk=None):
        org = self.get_object()

        from apps.alerts.models import Alert
        from apps.collectors.models import ConnectorConfig
        from apps.logs.models import NormalizedLog

        data = {
            "user_count": org.users.count(),
            "connector_count": ConnectorConfig.objects.filter(organization=org).count(),
            "active_connector_count": ConnectorConfig.objects.filter(organization=org, is_active=True).count(),
            "log_count": NormalizedLog.objects.filter(organization=org).count(),
            "open_alert_count": Alert.objects.filter(organization=org, status="open").count(),
        }
        return success_response(data=data, message="Statistiques de l'organisation.")

    @action(detail=False, methods=["get"])
    def overview(self, request):
        """Vue d'ensemble cross-org pour le dashboard super-admin."""
        from apps.users.models import User

        orgs = self.get_queryset()
        data = {
            "organization_count": orgs.count(),
            "active_organization_count": orgs.filter(is_active=True).count(),
            "total_user_count": User.objects.exclude(organization__isnull=True).count(),
            "platform_staff_count": User.objects.filter(is_superuser=True).count(),
        }
        return success_response(data=data, message="Vue d'ensemble plateforme.")
