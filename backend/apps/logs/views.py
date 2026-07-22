"""
Vues pour les logs bruts, normalisés et les statistiques.
"""
import logging
from datetime import timedelta

from django.db.models import Count, Max, Min, Q
from django.db.models.expressions import RawSQL
from django.db.models.functions import TruncDay, TruncHour
from django.utils import timezone
from django.utils.dateparse import parse_datetime
from rest_framework import filters, status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework.viewsets import ReadOnlyModelViewSet

from utils.pagination import LargeResultsPagination, StandardResultsPagination
from utils.permissions import IsAnalyst
from utils.response import error_response, success_response
from utils.tenant import OrganizationFilterBackend

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
        OrganizationFilterBackend,
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
        OrganizationFilterBackend,
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


# Champs sur lesquels calculer les facettes (valeurs les plus fréquentes) —
# équivalent des "interesting fields" de Splunk / des aggregations Elastic.
FACET_FIELDS = ["source_type", "severity", "action", "user_email", "source_ip", "geo_country", "outcome"]
# Champs texte pouvant être stockés en chaîne vide (à exclure des facettes en
# plus des NULL) — source_ip (inet) ne peut pas être une chaîne vide.
BLANK_EXCLUDABLE_FACET_FIELDS = {"source_type", "action", "user_email", "geo_country"}

# Paliers de largeur de bucket (secondes), du plus fin au plus grossier.
_INTERVAL_CANDIDATES_SECONDS = [
    30, 60, 300, 900, 1800, 3600, 3 * 3600, 6 * 3600, 12 * 3600,
    86400, 2 * 86400, 7 * 86400, 30 * 86400,
]


def _pick_interval_seconds(span_seconds: float) -> int:
    """Choisit la largeur de bucket visant ~60-100 barres, quelle que soit
    la plage temporelle — même principe que le timeline picker de
    Splunk/Kibana (résolution adaptative)."""
    if span_seconds <= 0:
        return 60
    for step in _INTERVAL_CANDIDATES_SECONDS:
        if span_seconds / step <= 100:
            return step
    return _INTERVAL_CANDIDATES_SECONDS[-1]


class LogHistogramView(APIView):
    """
    GET /api/logs/histogram/
    Histogramme temporel (bucketing adaptatif, empilé par sévérité) +
    facettes agrégées — filtré par les mêmes critères que
    /api/logs/normalized/ (recherche, sévérité multi, source, action,
    utilisateur, IP, plage de dates via event_time_from/event_time_to).

    Remplace le faux histogramme généré côté frontend (Math.sin() codé en
    dur, jamais connecté à aucune donnée réelle) par de vraies agrégations
    SQL portant sur l'ensemble des résultats correspondant aux filtres —
    pas seulement la page actuellement affichée.
    """

    permission_classes = [IsAnalyst]

    def get(self, request):
        user = request.user
        if user.is_superuser and user.organization_id is None:
            base_qs = NormalizedLog.objects.none()
        else:
            base_qs = NormalizedLog.objects.filter(organization_id=user.organization_id)

        filterset = NormalizedLogFilter(request.query_params, queryset=base_qs)
        if not filterset.is_valid():
            return error_response(
                message="Paramètres de filtre invalides.",
                errors=filterset.errors,
                http_status=status.HTTP_400_BAD_REQUEST,
            )
        queryset = filterset.qs

        # Bornes temporelles : celles du filtre si fournies, sinon les 24
        # dernières heures par défaut (cohérent avec le reste de l'app).
        now = timezone.now()
        event_from_raw = request.query_params.get("event_time_from")
        event_to_raw = request.query_params.get("event_time_to")
        range_from = (parse_datetime(event_from_raw) if event_from_raw else None) or (now - timedelta(hours=24))
        range_to = (parse_datetime(event_to_raw) if event_to_raw else None) or now

        span_seconds = max((range_to - range_from).total_seconds(), 1)
        requested_interval = request.query_params.get("interval")
        try:
            step_seconds = int(requested_interval) if requested_interval else _pick_interval_seconds(span_seconds)
        except ValueError:
            step_seconds = _pick_interval_seconds(span_seconds)
        step_seconds = max(step_seconds, 1)

        # Bucketing à largeur arbitraire : Django ne propose que des Trunc
        # fixes (Minute/Hour/Day...), donc expression SQL directe
        # équivalente à date_trunc mais paramétrable en secondes.
        bucket_expr = RawSQL(
            "to_timestamp(floor(extract(epoch from event_time) / %s) * %s)",
            [step_seconds, step_seconds],
        )

        rows = (
            queryset
            .annotate(bucket=bucket_expr)
            .values("bucket")
            .annotate(
                count=Count("id"),
                critical=Count("id", filter=Q(severity="critical")),
                high=Count("id", filter=Q(severity="high")),
                medium=Count("id", filter=Q(severity="medium")),
                low=Count("id", filter=Q(severity="low")),
                info=Count("id", filter=Q(severity="info")),
            )
            .order_by("bucket")
        )

        buckets = [
            {
                "t": row["bucket"].isoformat(),
                "count": row["count"],
                "critical": row["critical"],
                "high": row["high"],
                "medium": row["medium"],
                "low": row["low"],
                "info": row["info"],
            }
            for row in rows
            if row["bucket"] is not None
        ]

        facets = {}
        for field in FACET_FIELDS:
            field_qs = queryset.exclude(**{f"{field}__isnull": True})
            if field in BLANK_EXCLUDABLE_FACET_FIELDS:
                field_qs = field_qs.exclude(**{field: ""})
            top = field_qs.values(field).annotate(count=Count("id")).order_by("-count")[:8]
            facets[field] = [{"value": str(row[field]), "count": row["count"]} for row in top]

        return success_response(
            data={
                "total": queryset.count(),
                "interval_seconds": step_seconds,
                "range_from": range_from.isoformat(),
                "range_to": range_to.isoformat(),
                "buckets": buckets,
                "facets": facets,
            },
            message="Histogramme calculé.",
        )


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

        # Isolation multi-tenant : un APIView n'est pas couvert par
        # OrganizationFilterBackend (réservé aux ViewSets/GenericAPIView via
        # filter_queryset) — le scoping doit être fait explicitement ici.
        user = request.user
        if user.is_superuser and user.organization_id is None:
            org_logs = NormalizedLog.objects.none()
        else:
            org_logs = NormalizedLog.objects.filter(organization_id=user.organization_id)

        # Volume par heure — 24 dernières heures
        hourly_volume = (
            org_logs
            .filter(event_time__gte=last_24h)
            .annotate(hour=TruncHour("event_time"))
            .values("hour")
            .annotate(count=Count("id"))
            .order_by("hour")
        )

        # Volume par jour — 30 derniers jours
        daily_volume = (
            org_logs
            .filter(event_time__gte=last_30d)
            .annotate(day=TruncDay("event_time"))
            .values("day")
            .annotate(count=Count("id"))
            .order_by("day")
        )

        # Top 10 IP sources
        top_ips = (
            org_logs
            .filter(event_time__gte=last_24h, source_ip__isnull=False)
            .values("source_ip")
            .annotate(count=Count("id"))
            .order_by("-count")[:10]
        )

        # Top 10 utilisateurs
        top_users = (
            org_logs
            .filter(event_time__gte=last_24h, user_email__isnull=False)
            .values("user_email")
            .annotate(count=Count("id"))
            .order_by("-count")[:10]
        )

        # Répartition par action
        by_action = (
            org_logs
            .filter(event_time__gte=last_24h)
            .values("action")
            .annotate(count=Count("id"))
            .order_by("-count")
        )

        # Répartition par pays
        by_country = (
            org_logs
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


_PERIOD_CONFIG = {
    # période → (timedelta, fonction de troncature, format de clé de bucket)
    "1h": (timedelta(hours=1), "hour"),
    "24h": (timedelta(hours=24), "hour"),
    "7d": (timedelta(days=7), "day"),
    "30d": (timedelta(days=30), "day"),
}


class IPTrafficOverviewView(APIView):
    """
    GET /api/logs/ip-traffic/?period=24h
    Vue agrégée "qui contacte le système" — pensée comme un tableau de bord
    de trafic façon Grafana/observabilité réseau, mais entièrement native à
    Argus : classement des IP par volume, répartition par pays, chronologie
    globale, et un mini-historique par IP (sparkline) pour les IP les plus
    actives. `period` : 1h | 24h | 7d | 30d.
    """

    permission_classes = [IsAnalyst]

    def get(self, request):
        period = request.query_params.get("period", "24h")
        if period not in _PERIOD_CONFIG:
            return error_response(
                message=f"Période invalide. Valeurs acceptées : {list(_PERIOD_CONFIG.keys())}",
                http_status=status.HTTP_400_BAD_REQUEST,
            )
        delta, granularity = _PERIOD_CONFIG[period]
        now = timezone.now()
        cutoff = now - delta
        trunc_fn = TruncHour if granularity == "hour" else TruncDay

        user = request.user
        if user.is_superuser and user.organization_id is None:
            base_qs = NormalizedLog.objects.none()
        else:
            base_qs = NormalizedLog.objects.filter(organization_id=user.organization_id)

        period_qs = base_qs.filter(event_time__gte=cutoff)

        # ─── Résumé ────────────────────────────────────────────────────────
        total_requests = period_qs.count()
        unique_ips = period_qs.exclude(source_ip__isnull=True).values("source_ip").distinct().count()
        unique_countries = (
            period_qs.exclude(geo_country__isnull=True).values("geo_country").distinct().count()
        )

        # ─── Chronologie globale (comble les buckets vides à 0) ────────────
        raw_buckets = (
            period_qs
            .annotate(bucket=trunc_fn("event_time"))
            .values("bucket")
            .annotate(count=Count("id"))
            .order_by("bucket")
        )
        bucket_counts = {row["bucket"]: row["count"] for row in raw_buckets if row["bucket"]}
        expected_buckets = self._expected_buckets(cutoff, now, granularity)
        timeline = [
            {"bucket": b.isoformat(), "count": bucket_counts.get(b, 0)} for b in expected_buckets
        ]

        # ─── Répartition par pays ───────────────────────────────────────────
        country_rows = list(
            period_qs.exclude(geo_country__isnull=True).exclude(geo_country="")
            .values("geo_country")
            .annotate(count=Count("id"))
            .order_by("-count")[:15]
        )
        country_total = sum(r["count"] for r in country_rows) or 1
        by_country = [
            {
                "country_code": r["geo_country"],
                "count": r["count"],
                "percentage": round((r["count"] / country_total) * 100, 1),
            }
            for r in country_rows
        ]

        # ─── Top IP + détails (3 requêtes groupées, pas N+1) ───────────────
        top_ip_rows = list(
            period_qs.exclude(source_ip__isnull=True)
            .values("source_ip")
            .annotate(count=Count("id"))
            .order_by("-count")[:25]
        )
        top_ips_list = [r["source_ip"] for r in top_ip_rows]
        top_ips_data = self._build_top_ips(period_qs, top_ips_list, top_ip_rows, trunc_fn, expected_buckets)

        return Response({
            "period": period,
            "generated_at": now.isoformat(),
            "summary": {
                "total_requests": total_requests,
                "unique_ips": unique_ips,
                "unique_countries": unique_countries,
                "known_threats": sum(1 for ip in top_ips_data if ip["is_known_threat"]),
            },
            "timeline": timeline,
            "by_country": by_country,
            "top_ips": top_ips_data,
        })

    @staticmethod
    def _expected_buckets(cutoff, now, granularity) -> list:
        """Liste complète des buckets attendus sur la période, pour ne jamais
        avoir de trou dans le graphe temporel (une heure/jour sans trafic
        doit apparaître à 0, pas disparaître du graphe)."""
        buckets = []
        if granularity == "hour":
            current = cutoff.replace(minute=0, second=0, microsecond=0)
            step = timedelta(hours=1)
        else:
            current = cutoff.replace(hour=0, minute=0, second=0, microsecond=0)
            step = timedelta(days=1)
        while current <= now:
            buckets.append(current)
            current += step
        return buckets

    @staticmethod
    def _build_top_ips(period_qs, top_ips_list, top_ip_rows, trunc_fn, expected_buckets) -> list:
        if not top_ips_list:
            return []

        from apps.threat_intel.models import ThreatIndicator

        ip_qs = period_qs.filter(source_ip__in=top_ips_list)

        # Succès/échecs + première/dernière activité — 1 requête pour tous les IP.
        detail_rows = (
            ip_qs.values("source_ip")
            .annotate(
                success_count=Count("id", filter=Q(outcome="success")),
                failure_count=Count("id", filter=Q(outcome="failure")),
                first_seen=Min("event_time"),
                last_seen=Max("event_time"),
            )
        )
        details_by_ip = {r["source_ip"]: r for r in detail_rows}

        # Pays le plus fréquent par IP — 1 requête pour tous les IP (le
        # premier groupe rencontré par IP est le plus fréquent grâce au tri).
        country_rows = (
            ip_qs.exclude(geo_country__isnull=True).exclude(geo_country="")
            .values("source_ip", "geo_country")
            .annotate(count=Count("id"))
            .order_by("source_ip", "-count")
        )
        country_by_ip = {}
        for row in country_rows:
            country_by_ip.setdefault(row["source_ip"], row["geo_country"])

        # Sparkline (historique par bucket) — 1 requête pour tous les IP.
        spark_rows = (
            ip_qs
            .annotate(bucket=trunc_fn("event_time"))
            .values("source_ip", "bucket")
            .annotate(count=Count("id"))
            .order_by("source_ip", "bucket")
        )
        spark_by_ip: dict = {}
        for row in spark_rows:
            spark_by_ip.setdefault(row["source_ip"], {})[row["bucket"]] = row["count"]

        # IP déjà connues comme malveillantes par le référentiel CTI — 1 requête.
        malicious_ips = set(
            ThreatIndicator.objects.filter(
                indicator_type="ip", value__in=top_ips_list, is_malicious=True,
            ).values_list("value", flat=True)
        )

        # Ne garder que les derniers buckets pour la sparkline (compacte, ~12-24 points).
        spark_buckets = expected_buckets[-24:] if len(expected_buckets) > 24 else expected_buckets

        results = []
        for row in top_ip_rows:
            ip = row["source_ip"]
            detail = details_by_ip.get(ip, {})
            ip_sparkline = spark_by_ip.get(ip, {})
            results.append({
                "source_ip": ip,
                "count": row["count"],
                "geo_country": country_by_ip.get(ip),
                "success_count": detail.get("success_count", 0),
                "failure_count": detail.get("failure_count", 0),
                "first_seen": detail["first_seen"].isoformat() if detail.get("first_seen") else None,
                "last_seen": detail["last_seen"].isoformat() if detail.get("last_seen") else None,
                "is_known_threat": ip in malicious_ips,
                "sparkline": [ip_sparkline.get(b, 0) for b in spark_buckets],
            })
        return results


class LogsCleanupTask:
    """Tâche Celery de nettoyage (définie dans tasks.py)."""
    pass
