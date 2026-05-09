"""
Vues pour la gestion des alertes SOC.
"""
import logging
from datetime import timedelta

from django.db.models import Avg, Count, Q
from django.utils import timezone
from django_filters.rest_framework import DjangoFilterBackend
from rest_framework import filters, status
from rest_framework.decorators import action
from rest_framework.viewsets import ModelViewSet

from apps.users.models import AuditTrail
from utils.permissions import IsAnalyst
from utils.response import error_response, success_response

from .models import Alert, AlertComment
from .serializers import (
    AlertBriefSerializer,
    AlertCommentCreateSerializer,
    AlertCommentSerializer,
    AlertSerializer,
    AlertUpdateSerializer,
)

logger = logging.getLogger(__name__)


def get_client_ip(request) -> str:
    x_forwarded = request.META.get("HTTP_X_FORWARDED_FOR")
    if x_forwarded:
        return x_forwarded.split(",")[0].strip()
    return request.META.get("REMOTE_ADDR", "")


class AlertViewSet(ModelViewSet):
    """
    Gestion des alertes SOC.
    GET    /api/alerts/
    GET    /api/alerts/{id}/
    PATCH  /api/alerts/{id}/
    POST   /api/alerts/{id}/comments/
    GET    /api/alerts/{id}/comments/
    GET    /api/alerts/stats/
    """

    queryset = (
        Alert.objects
        .select_related("rule", "assigned_to")
        .prefetch_related("comments", "source_logs")
        .all()
    )
    permission_classes = [IsAnalyst]
    filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    filterset_fields = ["status", "severity", "assigned_to", "rule"]
    search_fields = ["title", "description"]
    ordering_fields = ["created_at", "severity", "status"]
    ordering = ["-created_at"]
    http_method_names = ["get", "patch", "post", "head", "options"]

    def get_serializer_class(self):
        if self.action == "partial_update":
            return AlertUpdateSerializer
        return AlertSerializer

    def get_queryset(self):
        queryset = super().get_queryset()
        date_from = self.request.query_params.get("date_from")
        date_to = self.request.query_params.get("date_to")
        if date_from:
            queryset = queryset.filter(created_at__gte=date_from)
        if date_to:
            queryset = queryset.filter(created_at__lte=date_to)
        return queryset

    def list(self, request, *args, **kwargs):
        queryset = self.filter_queryset(self.get_queryset())
        page = self.paginate_queryset(queryset)
        if page is not None:
            serializer = AlertBriefSerializer(page, many=True)
            return self.get_paginated_response(serializer.data)
        serializer = AlertBriefSerializer(queryset, many=True)
        return success_response(data=serializer.data, message="Liste des alertes.")

    def retrieve(self, request, *args, **kwargs):
        alert = self.get_object()
        return success_response(data=AlertSerializer(alert).data)

    def partial_update(self, request, *args, **kwargs):
        alert = self.get_object()
        old_status = alert.status
        serializer = AlertUpdateSerializer(alert, data=request.data, partial=True)
        if not serializer.is_valid():
            return error_response(message="Données invalides.", errors=serializer.errors)
        updated = serializer.save()
        AuditTrail.log(
            action="alert_update",
            user=request.user,
            target_model="Alert",
            target_id=alert.id,
            ip_address=get_client_ip(request),
            extra_data={
                "old_status": old_status,
                "new_status": updated.status,
                "changes": request.data,
            },
        )
        return success_response(
            data=AlertSerializer(updated).data,
            message="Alerte mise à jour.",
        )

    @action(detail=True, methods=["get", "post"], url_path="comments")
    def comments(self, request, pk=None):
        """GET/POST /api/alerts/{id}/comments/"""
        alert = self.get_object()

        if request.method == "GET":
            qs = alert.comments.select_related("author").order_by("created_at")
            page = self.paginate_queryset(qs)
            if page is not None:
                serializer = AlertCommentSerializer(page, many=True)
                return self.get_paginated_response(serializer.data)
            return success_response(
                data=AlertCommentSerializer(qs, many=True).data,
                message="Commentaires de l'alerte.",
            )

        # POST
        serializer = AlertCommentCreateSerializer(data=request.data)
        if not serializer.is_valid():
            return error_response(message="Données invalides.", errors=serializer.errors)
        comment = AlertComment.objects.create(
            alert=alert,
            author=request.user,
            content=serializer.validated_data["content"],
        )
        return success_response(
            data=AlertCommentSerializer(comment).data,
            message="Commentaire ajouté.",
            http_status=status.HTTP_201_CREATED,
        )

    @action(detail=False, methods=["get"], url_path="stats")
    def stats(self, request):
        """GET /api/alerts/stats/ — Métriques SOC."""
        now = timezone.now()
        last_24h = now - timedelta(hours=24)

        # Count par sévérité
        by_severity = (
            Alert.objects
            .values("severity")
            .annotate(count=Count("id"))
        )

        # Count par statut
        by_status = (
            Alert.objects
            .values("status")
            .annotate(count=Count("id"))
        )

        # MTTR — Mean Time To Resolve (en heures)
        resolved_alerts = Alert.objects.filter(
            status__in=("resolved", "false_positive"),
            resolved_at__isnull=False,
        )
        mttr_data = [a.time_to_resolve_hours for a in resolved_alerts if a.time_to_resolve_hours]
        mttr_avg = round(sum(mttr_data) / len(mttr_data), 2) if mttr_data else None

        # Alertes ouvertes depuis > 24h
        old_open = Alert.objects.filter(
            status__in=("open", "in_progress"),
            created_at__lt=last_24h,
        ).count()

        # Total alertes ouvertes
        total_open = Alert.objects.filter(status="open").count()

        # Taux de faux positifs
        total_resolved = Alert.objects.filter(status__in=("resolved", "false_positive")).count()
        false_positive_count = Alert.objects.filter(status="false_positive").count()
        fp_rate = round(false_positive_count / total_resolved * 100, 1) if total_resolved > 0 else 0.0

        return success_response(
            data={
                "by_severity": {item["severity"]: item["count"] for item in by_severity},
                "by_status": {item["status"]: item["count"] for item in by_status},
                "mttr_hours": mttr_avg,
                "open_alerts_older_than_24h": old_open,
                "total_open": total_open,
                "false_positive_rate_percent": fp_rate,
            },
            message="Statistiques des alertes SOC.",
        )
