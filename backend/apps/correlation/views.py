"""
Vues pour les règles de corrélation.
"""
import logging

from django_filters.rest_framework import DjangoFilterBackend
from rest_framework import filters, status
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework.viewsets import ModelViewSet

from utils.permissions import IsAdmin, IsAnalyst
from utils.response import created_response, error_response, no_content_response, success_response
from utils.tenant import OrganizationFilterBackend

from .mitre_attack import MITRE_ATTACK_REFERENCE, build_coverage_matrix
from .models import CorrelationRule
from .serializers import CorrelationRuleCreateSerializer, CorrelationRuleSerializer

logger = logging.getLogger(__name__)


class CorrelationRuleViewSet(ModelViewSet):
    """
    CRUD complet pour les règles de corrélation.
    GET    /api/correlation/rules/
    POST   /api/correlation/rules/
    GET    /api/correlation/rules/{id}/
    PUT    /api/correlation/rules/{id}/
    DELETE /api/correlation/rules/{id}/
    POST   /api/correlation/rules/{id}/toggle/
    POST   /api/correlation/rules/{id}/test/
    """

    queryset = CorrelationRule.objects.prefetch_related("matches").all()
    filter_backends = [OrganizationFilterBackend, DjangoFilterBackend, filters.SearchFilter]
    filterset_fields = ["is_active", "severity", "mitre_tactic"]
    search_fields = ["name", "description"]

    def get_serializer_class(self):
        if self.action in ("create", "update", "partial_update"):
            return CorrelationRuleCreateSerializer
        return CorrelationRuleSerializer

    def get_permissions(self):
        if self.action in ("create", "update", "partial_update", "destroy", "toggle"):
            return [IsAnalyst()]
        return [IsAnalyst()]

    def list(self, request, *args, **kwargs):
        queryset = self.filter_queryset(self.get_queryset())
        page = self.paginate_queryset(queryset)
        if page is not None:
            serializer = CorrelationRuleSerializer(page, many=True)
            return self.get_paginated_response(serializer.data)
        serializer = CorrelationRuleSerializer(queryset, many=True)
        return success_response(data=serializer.data, message="Liste des règles de corrélation.")

    def create(self, request, *args, **kwargs):
        serializer = CorrelationRuleCreateSerializer(data=request.data)
        if not serializer.is_valid():
            return error_response(message="Données invalides.", errors=serializer.errors)
        rule = serializer.save(created_by=request.user, organization=request.user.organization)
        from apps.users.models import AuditTrail
        AuditTrail.log(action="rule_create", user=request.user, target_model="CorrelationRule", target_id=rule.id)
        return created_response(
            data=CorrelationRuleSerializer(rule).data,
            message="Règle créée avec succès.",
        )

    def retrieve(self, request, *args, **kwargs):
        rule = self.get_object()
        return success_response(data=CorrelationRuleSerializer(rule).data)

    def update(self, request, *args, **kwargs):
        partial = kwargs.pop("partial", False)
        rule = self.get_object()
        serializer = CorrelationRuleCreateSerializer(rule, data=request.data, partial=partial)
        if not serializer.is_valid():
            return error_response(message="Données invalides.", errors=serializer.errors)
        rule = serializer.save()
        from apps.users.models import AuditTrail
        AuditTrail.log(action="rule_update", user=request.user, target_model="CorrelationRule", target_id=rule.id)
        return success_response(data=CorrelationRuleSerializer(rule).data, message="Règle mise à jour.")

    def destroy(self, request, *args, **kwargs):
        rule = self.get_object()
        from apps.users.models import AuditTrail
        AuditTrail.log(action="rule_delete", user=request.user, target_model="CorrelationRule", target_id=rule.id)
        rule.delete()
        return no_content_response("Règle supprimée.")

    @action(detail=True, methods=["post"], permission_classes=[IsAnalyst])
    def toggle(self, request, pk=None):
        """POST /api/correlation/rules/{id}/toggle/ — Active ou désactive la règle."""
        rule = self.get_object()
        rule.is_active = not rule.is_active
        rule.save(update_fields=["is_active"])
        state = "activée" if rule.is_active else "désactivée"
        from apps.users.models import AuditTrail
        AuditTrail.log(
            action=f"rule_{'activate' if rule.is_active else 'deactivate'}",
            user=request.user,
            target_model="CorrelationRule",
            target_id=rule.id,
        )
        return success_response(
            data={"is_active": rule.is_active},
            message=f"Règle '{rule.name}' {state}.",
        )

    @action(detail=True, methods=["post"], permission_classes=[IsAnalyst])
    def test(self, request, pk=None):
        """
        POST /api/correlation/rules/{id}/test/
        Teste la règle sur les 1000 derniers logs normalisés.
        """
        rule = self.get_object()
        try:
            from apps.correlation.engine import correlation_engine
            result = correlation_engine.test_rule(rule, max_logs=1000)
            return success_response(data=result, message="Test de règle effectué.")
        except Exception as exc:
            logger.exception("Erreur test règle %s : %s", rule.name, exc)
            return error_response(
                message=f"Erreur lors du test : {str(exc)}",
                http_status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )


class MitreAttackReferenceView(APIView):
    """GET /api/correlation/mitre-attack/ — référentiel ATT&CK complet."""

    permission_classes = [IsAnalyst]

    def get(self, request):
        return Response(MITRE_ATTACK_REFERENCE)


class MitreAttackCoverageView(APIView):
    """
    GET /api/correlation/mitre-attack/coverage/
    Matrice de couverture ATT&CK pour l'organisation de l'utilisateur :
    quelles tactiques/techniques sont couvertes par au moins une règle
    active. Concept de maturité SOC reconnu, absent des SIEM open source
    grand public par défaut.
    """

    permission_classes = [IsAnalyst]

    def get(self, request):
        matrix = build_coverage_matrix(request.user.organization_id)
        total = sum(len(t["techniques"]) for t in matrix)
        covered = sum(1 for t in matrix for tech in t["techniques"] if tech["covered"])
        return Response({
            "matrix": matrix,
            "coverage_percent": round((covered / total) * 100, 1) if total else 0,
            "covered_count": covered,
            "total_count": total,
        })
