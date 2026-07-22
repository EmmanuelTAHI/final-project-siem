"""API SOAR — gestion des playbooks et des exécutions."""
from django.db.models import Count, Q
from django.utils import timezone
from datetime import timedelta
from rest_framework import status
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework.viewsets import ModelViewSet, ReadOnlyModelViewSet

from utils.permissions import IsAdmin, IsAnalyst, IsAdminOrReadOnly
from .models import BlockedIP, Playbook, PlaybookExecution
from .serializers import BlockedIPSerializer, PlaybookExecutionSerializer, PlaybookSerializer
from .tasks import execute_playbook


class PlaybookViewSet(ModelViewSet):
    queryset = Playbook.objects.all()
    serializer_class = PlaybookSerializer
    permission_classes = [IsAdminOrReadOnly]
    filterset_fields = ["trigger_type", "is_active"]
    search_fields = ["name", "description"]
    ordering_fields = ["name", "execution_count", "created_at"]
    ordering = ["name"]

    @action(detail=True, methods=["post"])
    def toggle(self, request, pk=None):
        playbook = self.get_object()
        playbook.is_active = not playbook.is_active
        playbook.save(update_fields=["is_active"])
        return Response({"is_active": playbook.is_active})

    @action(detail=True, methods=["post"])
    def execute(self, request, pk=None):
        """Déclenchement manuel d'un playbook sur une alerte."""
        playbook = self.get_object()
        alert_id = request.data.get("alert_id")
        if not alert_id:
            return Response({"error": "alert_id requis"}, status=status.HTTP_400_BAD_REQUEST)

        task = execute_playbook.delay(str(playbook.id), str(alert_id), triggered_by="manual")
        return Response({"task_id": task.id, "status": "queued"})


class PlaybookExecutionViewSet(ReadOnlyModelViewSet):
    queryset = PlaybookExecution.objects.select_related("playbook", "alert")
    serializer_class = PlaybookExecutionSerializer
    permission_classes = [IsAnalyst]
    filterset_fields = ["status", "playbook", "triggered_by"]
    ordering = ["-started_at"]


class BlockedIPViewSet(ModelViewSet):
    """
    Blocages IP actifs sur la plateforme (appliqués par
    `utils.blocklist_middleware.BlockedIPMiddleware`).
    GET    /api/soar/blocked-ips/
    POST   /api/soar/blocked-ips/                (blocage manuel)
    POST   /api/soar/blocked-ips/{id}/unblock/    (lever le blocage — ex: faux positif)
    """
    queryset = BlockedIP.objects.all()
    serializer_class = BlockedIPSerializer
    permission_classes = [IsAnalyst]
    filterset_fields = ["is_active", "source"]
    ordering = ["-created_at"]

    def perform_create(self, serializer):
        serializer.save(organization=self.request.user.organization, source="manual")

    @action(detail=True, methods=["post"])
    def unblock(self, request, pk=None):
        blocked = self.get_object()
        blocked.is_active = False
        blocked.save(update_fields=["is_active"])
        from django.core.cache import cache
        cache.delete(f"blocked_ip:{blocked.ip_address}")
        return Response({"is_active": False})


class SOARStatsView(APIView):
    permission_classes = [IsAnalyst]

    def get(self, request):
        last_24h = timezone.now() - timedelta(hours=24)
        last_7d = timezone.now() - timedelta(days=7)

        org_id = request.user.organization_id
        playbooks = Playbook.objects.filter(organization_id=org_id)
        executions = PlaybookExecution.objects.filter(organization_id=org_id)
        stats = {
            "total_playbooks": playbooks.count(),
            "active_playbooks": playbooks.filter(is_active=True).count(),
            "executions_24h": executions.filter(started_at__gte=last_24h).count(),
            "executions_7d": executions.filter(started_at__gte=last_7d).count(),
            "success_rate": _compute_success_rate(executions),
            "by_status": list(
                executions.values("status").annotate(count=Count("id"))
            ),
            "top_playbooks": list(
                playbooks.order_by("-execution_count").values("name", "execution_count")[:5]
            ),
        }
        return Response(stats)


def _compute_success_rate(qs) -> float:
    total = qs.count()
    if total == 0:
        return 0.0
    success = qs.filter(status="success").count()
    return round((success / total) * 100, 1)
