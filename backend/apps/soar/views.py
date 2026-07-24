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


def _apply_real_block(blocked: BlockedIP) -> str:
    """
    Applique le blocage réseau réel (démon local ufw) pour une IP déjà
    bloquée au niveau applicatif (BlockedIP). Utilisé aussi bien pour le
    blocage manuel via dashboard que pour les playbooks SOAR, afin que
    "bloquer une IP" signifie toujours la même chose : requête applicative
    ET paquets réseau réellement rejetés, pas juste un 403 Django.
    Retourne "ok" / "failed" / "unavailable" (démon non configuré).
    """
    from django.conf import settings

    if not settings.SOAR_BLOCKING_ENABLED:
        return "disabled"

    if not settings.HOST_FIREWALL_URL:
        return "unavailable"

    duration_hours = 0.0
    if blocked.expires_at:
        remaining = (blocked.expires_at - timezone.now()).total_seconds() / 3600
        duration_hours = max(remaining, 0.01)

    import httpx

    try:
        with httpx.Client(timeout=10.0) as client:
            resp = client.post(
                f"{settings.HOST_FIREWALL_URL.rstrip('/')}/block",
                json={"ip": blocked.ip_address, "action": "block", "duration_hours": duration_hours},
                headers={"Authorization": f"Bearer {settings.HOST_FIREWALL_TOKEN}"},
            )
            resp.raise_for_status()
        return "ok"
    except httpx.HTTPError:
        return "failed"


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
        from django.conf import settings

        # Coupe-circuit global (période de tests/démo) : la ligne est créée
        # pour la traçabilité mais jamais active, donc jamais appliquée par
        # `BlockedIPMiddleware` — et aucun appel au démon réseau réel.
        extra = {} if settings.SOAR_BLOCKING_ENABLED else {"is_active": False}
        blocked = serializer.save(
            organization=self.request.user.organization, source="manual", **extra
        )
        self._network_block_result = _apply_real_block(blocked)

    def create(self, request, *args, **kwargs):
        response = super().create(request, *args, **kwargs)
        # Renseigne si le blocage réseau réel (ufw, pas juste applicatif) a
        # réussi — le frontend peut avertir l'utilisateur si le démon local
        # est injoignable au lieu de laisser croire à un blocage effectif.
        response.data["network_block"] = getattr(self, "_network_block_result", "unavailable")
        return response

    @action(detail=True, methods=["post"])
    def unblock(self, request, pk=None):
        blocked = self.get_object()
        blocked.is_active = False
        blocked.save(update_fields=["is_active"])
        from django.core.cache import cache
        cache.delete(f"blocked_ip:{blocked.ip_address}")

        # Lève aussi le blocage réseau réel (démon local ufw), pas seulement
        # la ligne applicative — sinon l'IP reste bloquée au niveau réseau
        # alors que l'UI affiche "débloqué" (faux positif rassurant).
        from django.conf import settings
        if settings.HOST_FIREWALL_URL:
            import httpx
            try:
                with httpx.Client(timeout=10.0) as client:
                    client.post(
                        f"{settings.HOST_FIREWALL_URL.rstrip('/')}/unblock",
                        json={"ip": blocked.ip_address},
                        headers={"Authorization": f"Bearer {settings.HOST_FIREWALL_TOKEN}"},
                    )
            except httpx.HTTPError:
                pass  # le blocage applicatif est déjà levé ; ne pas faire échouer la requête pour ça

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
