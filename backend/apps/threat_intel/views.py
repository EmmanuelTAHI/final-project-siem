"""
API Threat Intelligence — indicateurs CTI et logs enrichis.
"""
from django.db.models import Avg, Count, Q
from django.utils import timezone
from datetime import timedelta
from rest_framework import status
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.viewsets import ModelViewSet, ReadOnlyModelViewSet
from rest_framework.views import APIView

from utils.permissions import IsAnalyst, IsViewer
from .models import Asset, AssetVulnerability, CVERecord, EnrichedLog, ThreatIndicator
from .serializers import (
    AssetSerializer,
    AssetVulnerabilitySerializer,
    CVERecordSerializer,
    EnrichedLogSerializer,
    ThreatIndicatorSerializer,
)
from .tasks import (
    correlate_cve_with_assets,
    enrich_logs_with_cti,
    sync_cisa_kev,
    sync_community_threat_feeds,
    sync_nvd_recent_cves,
)


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
        from apps.threat_intel.services import (
            abuseipdb,
            criminalip,
            ip_enrichment,
            shodan_svc,
            virustotal,
        )

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
            results["criminalip"] = criminalip.summarize(criminalip.check_ip(value))
            results["shodan"] = shodan_svc.summarize(shodan_svc.host_info(value))
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

        cip = results.get("criminalip") or {}
        if cip:
            inb = cip.get("inbound_score")
            if cip.get("is_malicious") or (isinstance(inb, (int, float)) and inb >= 75):
                score = max(score, 85)
                reasons.append(f"CriminalIP : IP classée malveillante (score entrant {inb})")
            elif cip.get("is_scanner"):
                score = max(score, 55)
                reasons.append("CriminalIP : scanner connu")
            elif cip.get("is_tor") or cip.get("is_vpn") or cip.get("is_proxy"):
                score = max(score, 45)
                reasons.append("CriminalIP : Tor / VPN / proxy détecté")

        shodan = results.get("shodan") or {}
        if shodan.get("vuln_count"):
            score = max(score, 50)
            reasons.append(f"Shodan : {shodan['vuln_count']} vulnérabilité(s) connue(s) exposée(s)")
        elif shodan.get("ports"):
            reasons.append(f"Shodan : {len(shodan['ports'])} port(s) ouvert(s) exposé(s)")

        geo = results.get("geo") or {}
        if geo:
            if geo.get("hosting"):
                score = max(score, 30)
                reasons.append(f"Réseau : hébergeur / datacenter ({geo.get('org') or geo.get('isp') or '—'})")
            if geo.get("proxy"):
                score = max(score, 45)
                reasons.append("Réseau : proxy / VPN / anonymiseur détecté")

        responded = bool(geo or cip or shodan or abuse or vt) or (
            internal and internal.get("seen") is not None
        )
        if score >= 75:
            level = "malicious"
        elif score >= 40:
            level = "suspicious"
        elif responded:
            level = "clean"
        else:
            level = "unknown"

        return {"level": level, "score": score, "reasons": reasons}

    @action(detail=False, methods=["post"])
    def trigger_enrichment(self, request):
        """Lance manuellement l'enrichissement CTI."""
        task = enrich_logs_with_cti.delay()
        return Response({"task_id": task.id, "status": "queued"})

    @action(detail=False, methods=["post"])
    def trigger_community_sync(self, request):
        """Lance manuellement la synchronisation des flux communautaires (URLhaus, Feodo Tracker)."""
        task = sync_community_threat_feeds.delay()
        return Response({"task_id": task.id, "status": "queued"})


class CVERecordViewSet(ReadOnlyModelViewSet):
    """
    Référentiel de vulnérabilités (NVD + CISA KEV), synchronisé
    automatiquement. C'est la réponse directe à "un SIEM par règles ne sait
    rien tant qu'on ne lui a pas donné les données à l'avance" : ce
    référentiel se met à jour tout seul, en continu.
    """

    queryset = CVERecord.objects.all()
    serializer_class = CVERecordSerializer
    permission_classes = [IsAnalyst]
    filterset_fields = ["is_kev", "severity"]
    search_fields = ["cve_id", "description", "vendor_project", "product"]
    ordering_fields = ["cvss_score", "published_date", "kev_date_added"]
    ordering = ["-is_kev", "-cvss_score"]

    @action(detail=False, methods=["post"])
    def trigger_sync(self, request):
        """Lance manuellement la synchronisation CVE (NVD) + KEV (CISA) + corrélation actifs."""
        kev_task = sync_cisa_kev.delay()
        nvd_task = sync_nvd_recent_cves.delay()
        return Response({
            "kev_task_id": kev_task.id,
            "nvd_task_id": nvd_task.id,
            "status": "queued",
        })

    @action(detail=False, methods=["get"])
    def stats(self, request):
        qs = CVERecord.objects.all()
        return Response({
            "total": qs.count(),
            "kev_count": qs.filter(is_kev=True).count(),
            "critical_count": qs.filter(severity="critical").count(),
            "high_count": qs.filter(severity="high").count(),
            "ransomware_associated": qs.filter(kev_ransomware_use=True).count(),
        })


class AssetViewSet(ModelViewSet):
    """Inventaire d'actifs de l'organisation, base de la corrélation CVE."""

    queryset = Asset.objects.all()
    serializer_class = AssetSerializer
    permission_classes = [IsAnalyst]
    filterset_fields = ["asset_type", "criticality"]
    search_fields = ["name", "vendor", "product", "hostname"]

    def perform_create(self, serializer):
        serializer.save(organization=self.request.user.organization, source="manual")

    @action(detail=False, methods=["post"])
    def trigger_correlation(self, request):
        """Relance manuellement la corrélation CVE ↔ actifs pour toute la plateforme."""
        task = correlate_cve_with_assets.delay()
        return Response({"task_id": task.id, "status": "queued"})


class AssetVulnerabilityViewSet(ReadOnlyModelViewSet):
    queryset = AssetVulnerability.objects.select_related("asset", "cve").all()
    serializer_class = AssetVulnerabilitySerializer
    permission_classes = [IsAnalyst]
    filterset_fields = ["status"]
    ordering = ["-matched_at"]

    @action(detail=True, methods=["patch"])
    def status(self, request, pk=None):
        """PATCH /api/threat-intel/asset-vulnerabilities/{id}/status/ — change le statut de traitement."""
        obj = self.get_object()
        new_status = request.data.get("status")
        valid = [c[0] for c in AssetVulnerability.STATUS_CHOICES]
        if new_status not in valid:
            return Response({"error": f"Statut invalide. Valeurs: {valid}"}, status=status.HTTP_400_BAD_REQUEST)
        obj.status = new_status
        obj.save(update_fields=["status"])
        return Response(AssetVulnerabilitySerializer(obj).data)


class EnrichedLogViewSet(ReadOnlyModelViewSet):
    queryset = EnrichedLog.objects.select_related("log").prefetch_related("indicators")
    serializer_class = EnrichedLogSerializer
    permission_classes = [IsAnalyst]
    filterset_fields = ["is_threat"]
    ordering = ["-enriched_at"]


class GeoFlagsView(APIView):
    """
    Géolocalisation légère (code pays uniquement) pour afficher un drapeau à
    côté d'une IP dans l'UI (alertes, logs, trafic…). Volontairement séparée
    du lookup CTI complet (`ThreatIndicatorViewSet.lookup`, POST, lourd —
    AbuseIPDB/VirusTotal/CriminalIP/Shodan) : ici on ne veut que le pays, vite
    et pour beaucoup d'IP à la fois, donc mise en cache longue durée par IP
    (ip-api.com est limité à 45 req/min sans clé).
    GET /api/threat-intel/geo-flags/?ips=1.2.3.4,5.6.7.8
    """
    permission_classes = [IsViewer]

    def get(self, request):
        from django.core.cache import cache
        from apps.threat_intel.services import ip_enrichment

        raw = request.query_params.get("ips", "")
        ips = [ip.strip() for ip in raw.split(",") if ip.strip()][:100]

        result = {}
        for ip in ips:
            cache_key = f"geo_flag:{ip}"
            cached = cache.get(cache_key)
            if cached is not None:
                result[ip] = cached
                continue

            geo = ip_enrichment.geo_lookup(ip)
            entry = {
                "country_code": geo.get("countryCode") or None,
                "country": geo.get("country") or None,
            }
            # 7 jours : le pays d'une IP ne change quasiment jamais, inutile
            # de re-taper ip-api.com à chaque rechargement de page.
            cache.set(cache_key, entry, timeout=60 * 60 * 24 * 7)
            result[ip] = entry

        return Response(result)


class CTIStatsView(APIView):
    permission_classes = [IsAnalyst]

    def get(self, request):
        last_24h = timezone.now() - timedelta(hours=24)
        last_7d = timezone.now() - timedelta(days=7)

        # ThreatIndicator est un référentiel CTI partagé (pas de notion de
        # tenant) ; EnrichedLog en revanche porte les données de l'org.
        indicators = ThreatIndicator.objects.all()
        enriched = EnrichedLog.objects.filter(organization_id=request.user.organization_id)

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
