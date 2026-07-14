"""
API Threat Hunting — interface de recherche avancée sur les NormalizedLogs.
"""
from datetime import timedelta

from django.utils import timezone
from rest_framework import status
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework.viewsets import ModelViewSet

from utils.permissions import IsAnalyst, IsAdminOrReadOnly
from .models import HuntingQuery, HuntingResult
from .serializers import HuntingQuerySerializer


ALLOWED_FIELDS = {
    "action", "outcome", "severity", "source_type", "geo_country", "user_email",
    "source_ip", "destination_ip", "resource", "user_agent",
}


class HuntingQueryViewSet(ModelViewSet):
    queryset = HuntingQuery.objects.all()
    serializer_class = HuntingQuerySerializer
    permission_classes = [IsAnalyst]
    search_fields = ["name", "description", "mitre_tactic"]
    ordering = ["-updated_at"]

    @action(detail=True, methods=["post"])
    def execute(self, request, pk=None):
        """Exécute une requête de chasse et retourne les logs correspondants."""
        query_obj = self.get_object()
        return _run_hunt(query_obj, request, organization_id=request.user.organization_id)

    @action(detail=True, methods=["get"])
    def results(self, request, pk=None):
        """Retourne les résultats de la dernière exécution."""
        query_obj = self.get_object()
        from apps.logs.serializers import NormalizedLogSerializer
        results = (
            HuntingResult.objects.filter(query=query_obj)
            .select_related("log")
            .order_by("-executed_at")[:500]
        )
        logs = [r.log for r in results]
        return Response({
            "count": len(logs),
            "results": NormalizedLogSerializer(logs, many=True).data,
        })


class HuntView(APIView):
    """
    POST /api/hunting/run/
    Exécution d'une requête de chasse ad-hoc sans la sauvegarder.
    """
    permission_classes = [IsAnalyst]

    def post(self, request):
        params = request.data.get("params", {})
        limit = int(request.data.get("limit", 500))
        return Response(_execute_hunt(params, limit=limit, organization_id=request.user.organization_id))


def _run_hunt(query_obj: HuntingQuery, request, organization_id):
    from apps.logs.serializers import NormalizedLogSerializer

    result = _execute_hunt(query_obj.query_params, organization_id=organization_id)
    logs_data = result["results"]

    query_obj.last_run_at = timezone.now()
    query_obj.last_results_count = result["count"]
    query_obj.run_count += 1
    query_obj.save(update_fields=["last_run_at", "last_results_count", "run_count"])

    return Response(result)


def _execute_hunt(params: dict, organization_id, limit: int = 500) -> dict:
    """
    Exécute une requête de chasse sur NormalizedLog, strictement limitée à
    l'organisation de l'utilisateur appelant (isolation multi-tenant).
    Filtres supportés: action, outcome, severity, source_type, geo_country,
    user_email, source_ip, destination_ip, date_from, date_to, extra_fields_contains.
    """
    from apps.logs.models import NormalizedLog
    from apps.logs.serializers import NormalizedLogSerializer

    qs = NormalizedLog.objects.filter(organization_id=organization_id).order_by("-event_time")

    for field in ALLOWED_FIELDS:
        val = params.get(field)
        if val:
            if isinstance(val, list):
                qs = qs.filter(**{f"{field}__in": val})
            else:
                qs = qs.filter(**{field: val})

    date_from = params.get("date_from")
    date_to = params.get("date_to")
    if date_from:
        qs = qs.filter(event_time__gte=date_from)
    if date_to:
        qs = qs.filter(event_time__lte=date_to)

    extra = params.get("extra_fields_contains")
    if extra and isinstance(extra, dict):
        for k, v in extra.items():
            qs = qs.filter(**{f"extra_fields__{k}": v})

    count = qs.count()
    logs = qs[:limit]
    return {
        "count": count,
        "returned": min(count, limit),
        "results": NormalizedLogSerializer(logs, many=True).data,
    }
