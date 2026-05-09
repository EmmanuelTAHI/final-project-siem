"""
API Threat Intelligence — indicateurs CTI et logs enrichis.
"""
from django.db.models import Avg, Count, Q
from django.utils import timezone
from datetime import timedelta
from rest_framework import status
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.viewsets import ReadOnlyModelViewSet
from rest_framework.views import APIView

from utils.permissions import IsAnalyst
from .models import EnrichedLog, ThreatIndicator
from .serializers import EnrichedLogSerializer, ThreatIndicatorSerializer
from .tasks import enrich_logs_with_cti


class ThreatIndicatorViewSet(ReadOnlyModelViewSet):
    queryset = ThreatIndicator.objects.all()
    serializer_class = ThreatIndicatorSerializer
    permission_classes = [IsAnalyst]
    filterset_fields = ["indicator_type", "source", "is_malicious"]
    search_fields = ["value", "tags"]
    ordering_fields = ["reputation_score", "last_seen", "first_seen"]
    ordering = ["-reputation_score"]

    @action(detail=False, methods=["post"])
    def lookup(self, request):
        """Lookup manuel d'un indicateur (IP, domaine, hash)."""
        from apps.threat_intel.services import abuseipdb, virustotal

        value = request.data.get("value", "")
        itype = request.data.get("type", "ip")

        if not value:
            return Response({"error": "value requis"}, status=status.HTTP_400_BAD_REQUEST)

        results = {}
        if itype == "ip":
            results["abuseipdb"] = abuseipdb.check_ip(value)
            results["virustotal"] = virustotal.analyze_ip(value)
        elif itype == "domain":
            results["virustotal"] = virustotal.analyze_domain(value)
        elif itype in ("hash_md5", "hash_sha256"):
            results["virustotal"] = virustotal.analyze_hash(value)

        return Response({"value": value, "type": itype, "results": results})

    @action(detail=False, methods=["post"])
    def trigger_enrichment(self, request):
        """Lance manuellement l'enrichissement CTI."""
        task = enrich_logs_with_cti.delay()
        return Response({"task_id": task.id, "status": "queued"})


class EnrichedLogViewSet(ReadOnlyModelViewSet):
    queryset = EnrichedLog.objects.select_related("log").prefetch_related("indicators")
    serializer_class = EnrichedLogSerializer
    permission_classes = [IsAnalyst]
    filterset_fields = ["is_threat"]
    ordering = ["-enriched_at"]


class CTIStatsView(APIView):
    permission_classes = [IsAnalyst]

    def get(self, request):
        last_24h = timezone.now() - timedelta(hours=24)
        last_7d = timezone.now() - timedelta(days=7)

        indicators = ThreatIndicator.objects.all()
        enriched = EnrichedLog.objects.all()

        stats = {
            "total_indicators": indicators.count(),
            "malicious_indicators": indicators.filter(is_malicious=True).count(),
            "threats_24h": enriched.filter(is_threat=True, enriched_at__gte=last_24h).count(),
            "threats_7d": enriched.filter(is_threat=True, enriched_at__gte=last_7d).count(),
            "avg_score_malicious": indicators.filter(is_malicious=True).aggregate(
                avg=Avg("reputation_score")
            )["avg"] or 0,
            "by_source": list(
                indicators.values("source").annotate(count=Count("id")).order_by("-count")
            ),
            "by_type": list(
                indicators.values("indicator_type").annotate(count=Count("id")).order_by("-count")
            ),
            "top_malicious_ips": list(
                indicators.filter(indicator_type="ip", is_malicious=True)
                .order_by("-reputation_score")
                .values("value", "reputation_score", "source")[:10]
            ),
        }
        return Response(stats)
