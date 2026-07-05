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
        from apps.threat_intel.services import abuseipdb, ip_enrichment, virustotal

        value = (request.data.get("value", "") or "").strip()
        itype = request.data.get("type", "ip")

        if not value:
            return Response({"error": "value requis"}, status=status.HTTP_400_BAD_REQUEST)

        results = {}
        if itype == "ip":
            # Sources sans clé API — renvoient toujours quelque chose d'utile
            results["geo"] = ip_enrichment.geo_lookup(value)
            results["internal"] = ip_enrichment.internal_reputation(value)
            # Sources externes (vides si clé non configurée)
            results["abuseipdb"] = abuseipdb.check_ip(value)
            results["virustotal"] = virustotal.analyze_ip(value)
        elif itype == "domain":
            results["virustotal"] = virustotal.analyze_domain(value)
        elif itype in ("hash_md5", "hash_sha256"):
            results["virustotal"] = virustotal.analyze_hash(value)

        verdict = self._compute_verdict(itype, results)
        return Response({"value": value, "type": itype, "results": results, "verdict": verdict})

    @staticmethod
    def _compute_verdict(itype: str, results: dict) -> dict:
        """
        Verdict de synthèse combinant toutes les sources disponibles.
        Fonctionne même sans clé API grâce à l'empreinte interne et au réseau.
        Niveaux : malicious > suspicious > clean > unknown.
        """
        score = 0
        reasons = []

        abuse = results.get("abuseipdb") or {}
        if abuse:
            conf = int(abuse.get("abuseConfidenceScore", 0) or 0)
            reports = int(abuse.get("totalReports", 0) or 0)
            if conf >= 75:
                score = max(score, 90)
                reasons.append(f"AbuseIPDB : confiance d'abus {conf}/100 ({reports} signalements)")
            elif conf >= 25 or reports > 0:
                score = max(score, 55)
                reasons.append(f"AbuseIPDB : {reports} signalement(s), confiance {conf}/100")

        vt = results.get("virustotal") or {}
        stats = (vt.get("attributes", {}) or {}).get("last_analysis_stats", {}) or {}
        vt_mal = int(stats.get("malicious", 0) or 0)
        vt_susp = int(stats.get("suspicious", 0) or 0)
        if vt_mal >= 5:
            score = max(score, 90)
            reasons.append(f"VirusTotal : {vt_mal} moteurs antivirus le classent malveillant")
        elif vt_mal + vt_susp >= 1:
            score = max(score, 55)
            reasons.append(f"VirusTotal : {vt_mal} malveillant / {vt_susp} suspect")

        internal = results.get("internal") or {}
        if internal.get("seen"):
            failures = int(internal.get("login_failures", 0) or 0)
            alerts = int(internal.get("alert_count", 0) or 0)
            if alerts > 0:
                score = max(score, 80)
                reasons.append(f"Empreinte interne : cette IP a déclenché {alerts} alerte(s) sur VOTRE infrastructure")
            elif failures >= 5:
                score = max(score, 60)
                reasons.append(f"Empreinte interne : {failures} échecs de connexion observés localement")
            elif internal.get("total_events", 0) > 0:
                score = max(score, 20)
                reasons.append("Empreinte interne : IP déjà observée dans vos logs")

        geo = results.get("geo") or {}
        if geo:
            if geo.get("hosting"):
                score = max(score, max(score, 30))
                reasons.append(f"Réseau : hébergeur / datacenter ({geo.get('org') or geo.get('isp') or '—'})")
            if geo.get("proxy"):
                score = max(score, 45)
                reasons.append("Réseau : proxy / VPN / anonymiseur détecté")

        if score >= 75:
            level = "malicious"
        elif score >= 40:
            level = "suspicious"
        elif score > 0 or geo or (internal and internal.get("seen") is not None):
            level = "clean"
        else:
            level = "unknown"

        return {"level": level, "score": score, "reasons": reasons}

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
