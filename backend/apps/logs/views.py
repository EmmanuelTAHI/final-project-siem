"""
Vues pour les logs bruts, normalisés et les statistiques.
"""
import logging
from datetime import timedelta

from django.db.models import Count
from django.db.models.functions import TruncHour, TruncDay
from django.utils import timezone
from rest_framework import filters
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework.viewsets import ReadOnlyModelViewSet

from utils.pagination import LargeResultsPagination, StandardResultsPagination
from utils.permissions import IsAnalyst
from utils.response import success_response

from .filters import NormalizedLogFilter, RawLogFilter
from .models import NormalizedLog, RawLog
from .serializers import NormalizedLogSerializer, RawLogSerializer

logger = logging.getLogger(__name__)


class RawLogViewSet(ReadOnlyModelViewSet):
    """
    Logs bruts — lecture seule.
    GET /api/logs/raw/
    GET /api/logs/raw/{id}/
    """

    queryset = RawLog.objects.select_related("connector").all()
    serializer_class = RawLogSerializer
    permission_classes = [IsAnalyst]
    pagination_class = StandardResultsPagination
    filterset_class = RawLogFilter
    filter_backends = [
        __import__("django_filters.rest_framework", fromlist=["DjangoFilterBackend"]).DjangoFilterBackend,
        filters.OrderingFilter,
    ]
    ordering_fields = ["received_at"]
    ordering = ["-received_at"]

    def retrieve(self, request, *args, **kwargs):
        log = self.get_object()
        return success_response(data=self.get_serializer(log).data)


class NormalizedLogViewSet(ReadOnlyModelViewSet):
    """
    Logs normalisés — lecture seule, tri par event_time DESC.
    GET /api/logs/normalized/
    GET /api/logs/normalized/{id}/
    """

    queryset = NormalizedLog.objects.all()
    serializer_class = NormalizedLogSerializer
    permission_classes = [IsAnalyst]
    pagination_class = LargeResultsPagination
    filterset_class = NormalizedLogFilter
    filter_backends = [
        __import__("django_filters.rest_framework", fromlist=["DjangoFilterBackend"]).DjangoFilterBackend,
        filters.SearchFilter,
        filters.OrderingFilter,
    ]
    search_fields = ["user_email", "source_ip", "action", "resource"]
    ordering_fields = ["event_time", "severity", "indexed_at"]
    ordering = ["-event_time"]

    def retrieve(self, request, *args, **kwargs):
        log = self.get_object()
        return success_response(data=self.get_serializer(log).data)


class LogStatsView(APIView):
    """
    GET /api/logs/stats/
    Statistiques globales sur les logs.
    """

    permission_classes = [IsAnalyst]

    def get(self, request):
        now = timezone.now()
        last_24h = now - timedelta(hours=24)
        last_30d = now - timedelta(days=30)

        # Volume par heure — 24 dernières heures
        hourly_volume = (
            NormalizedLog.objects
            .filter(event_time__gte=last_24h)
            .annotate(hour=TruncHour("event_time"))
            .values("hour")
            .annotate(count=Count("id"))
            .order_by("hour")
        )

        # Volume par jour — 30 derniers jours
        daily_volume = (
            NormalizedLog.objects
            .filter(event_time__gte=last_30d)
            .annotate(day=TruncDay("event_time"))
            .values("day")
            .annotate(count=Count("id"))
            .order_by("day")
        )

        # Top 10 IP sources
        top_ips = (
            NormalizedLog.objects
            .filter(event_time__gte=last_24h, source_ip__isnull=False)
            .values("source_ip")
            .annotate(count=Count("id"))
            .order_by("-count")[:10]
        )

        # Top 10 utilisateurs
        top_users = (
            NormalizedLog.objects
            .filter(event_time__gte=last_24h, user_email__isnull=False)
            .values("user_email")
            .annotate(count=Count("id"))
            .order_by("-count")[:10]
        )

        # Répartition par action
        by_action = (
            NormalizedLog.objects
            .filter(event_time__gte=last_24h)
            .values("action")
            .annotate(count=Count("id"))
            .order_by("-count")
        )

        # Répartition par pays
        by_country = (
            NormalizedLog.objects
            .filter(event_time__gte=last_24h, geo_country__isnull=False)
            .values("geo_country")
            .annotate(count=Count("id"))
            .order_by("-count")[:20]
        )

        return success_response(
            data={
                "hourly_volume_24h": list(
                    {"hour": h["hour"].isoformat(), "count": h["count"]} for h in hourly_volume
                ),
                "daily_volume_30d": list(
                    {"day": d["day"].isoformat(), "count": d["count"]} for d in daily_volume
                ),
                "top_source_ips": list(top_ips),
                "top_users": list(top_users),
                "by_action": list(by_action),
                "by_country": list(by_country),
            },
            message="Statistiques des logs calculées.",
        )


class LogsCleanupTask:
    """Tâche Celery de nettoyage (définie dans tasks.py)."""
    pass
