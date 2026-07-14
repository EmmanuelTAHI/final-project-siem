"""
Vues du tableau de bord SOC.
KPIs en temps réel, timeline, top menaces, carte géographique.
"""
import logging
from datetime import timedelta

from django.db.models import Count, Q
from django.db.models.functions import TruncDay, TruncHour
from django.utils import timezone
from rest_framework.permissions import IsAuthenticated
from rest_framework.views import APIView

from utils.response import success_response

logger = logging.getLogger(__name__)


class DashboardSummaryView(APIView):
    """
    GET /api/dashboard/summary/
    KPIs en temps réel pour le tableau de bord SOC.
    """

    permission_classes = [IsAuthenticated]

    def get(self, request):
        from apps.alerts.models import Alert
        from apps.collectors.models import ConnectorConfig
        from apps.logs.models import NormalizedLog
        from apps.ml.models import Prediction

        now = timezone.now()
        last_24h = now - timedelta(hours=24)
        org_id = request.user.organization_id

        alerts_qs = Alert.objects.filter(organization_id=org_id)
        logs_qs = NormalizedLog.objects.filter(organization_id=org_id)
        connectors_qs = ConnectorConfig.objects.filter(organization_id=org_id)
        predictions_qs = Prediction.objects.filter(organization_id=org_id)

        # ─── Alertes ouvertes ─────────────────────────────────────────────────
        open_alerts = alerts_qs.filter(status="open")
        total_open = open_alerts.count()
        open_by_severity = {
            item["severity"]: item["count"]
            for item in open_alerts.values("severity").annotate(count=Count("id"))
        }

        # ─── Logs collectés dans les 24 dernières heures ──────────────────────
        logs_24h = logs_qs.filter(event_time__gte=last_24h).count()

        # ─── Connecteurs ──────────────────────────────────────────────────────
        total_connectors = connectors_qs.count()
        active_connectors = connectors_qs.filter(is_active=True).count()

        # ─── Anomalies ML dans les 24 dernières heures ────────────────────────
        ml_anomalies_24h = predictions_qs.filter(
            is_anomaly=True,
            predicted_at__gte=last_24h,
        ).count()

        # ─── Taux de faux positifs ────────────────────────────────────────────
        total_resolved = alerts_qs.filter(
            status__in=("resolved", "false_positive")
        ).count()
        false_positives = alerts_qs.filter(status="false_positive").count()
        fp_rate = round(false_positives / total_resolved * 100, 1) if total_resolved > 0 else 0.0

        # ─── Alertes par sévérité (toutes) ────────────────────────────────────
        all_alerts_by_severity = {
            item["severity"]: item["count"]
            for item in alerts_qs.values("severity").annotate(count=Count("id"))
        }

        return success_response(
            data={
                "alerts": {
                    "total_open": total_open,
                    "open_by_severity": open_by_severity,
                    "all_by_severity": all_alerts_by_severity,
                    "false_positive_rate_percent": fp_rate,
                },
                "logs": {
                    "collected_last_24h": logs_24h,
                },
                "connectors": {
                    "active": active_connectors,
                    "total": total_connectors,
                    "inactive": total_connectors - active_connectors,
                },
                "ml": {
                    "anomalies_last_24h": ml_anomalies_24h,
                },
                "generated_at": now.isoformat(),
            },
            message="KPIs du tableau de bord SOC.",
        )


class DashboardTimelineView(APIView):
    """
    GET /api/dashboard/timeline/?period=24h|7d|30d
    Courbe temporelle des logs et alertes sur une période.
    """

    permission_classes = [IsAuthenticated]

    def get(self, request):
        from apps.alerts.models import Alert
        from apps.logs.models import NormalizedLog

        period = request.query_params.get("period", "24h")
        now = timezone.now()

        period_map = {
            "24h": (timedelta(hours=24), TruncHour, "hour"),
            "7d": (timedelta(days=7), TruncDay, "day"),
            "30d": (timedelta(days=30), TruncDay, "day"),
        }

        if period not in period_map:
            period = "24h"

        delta, trunc_fn, trunc_label = period_map[period]
        since = now - delta
        org_id = request.user.organization_id

        # Volume de logs par unité de temps
        log_timeline = (
            NormalizedLog.objects
            .filter(organization_id=org_id, event_time__gte=since)
            .annotate(time_bucket=trunc_fn("event_time"))
            .values("time_bucket")
            .annotate(count=Count("id"))
            .order_by("time_bucket")
        )

        # Volume d'alertes par unité de temps
        alert_timeline = (
            Alert.objects
            .filter(organization_id=org_id, created_at__gte=since)
            .annotate(time_bucket=trunc_fn("created_at"))
            .values("time_bucket")
            .annotate(count=Count("id"))
            .order_by("time_bucket")
        )

        return success_response(
            data={
                "period": period,
                "logs": [
                    {"time": item["time_bucket"].isoformat(), "count": item["count"]}
                    for item in log_timeline
                ],
                "alerts": [
                    {"time": item["time_bucket"].isoformat(), "count": item["count"]}
                    for item in alert_timeline
                ],
            },
            message=f"Timeline sur {period}.",
        )


class DashboardTopThreatsView(APIView):
    """
    GET /api/dashboard/top-threats/
    Top 10 règles de corrélation les plus déclenchées.
    """

    permission_classes = [IsAuthenticated]

    def get(self, request):
        from apps.correlation.models import CorrelationRule

        top_rules = (
            CorrelationRule.objects
            .filter(organization_id=request.user.organization_id)
            .annotate(alert_count=Count("alerts"))
            .order_by("-alert_count")[:10]
        )

        data = [
            {
                "rule_id": str(rule.id),
                "rule_name": rule.name,
                "severity": rule.severity,
                "mitre_tactic": rule.mitre_tactic,
                "mitre_technique": rule.mitre_technique,
                "alert_count": rule.alert_count,
                "is_active": rule.is_active,
            }
            for rule in top_rules
        ]

        return success_response(
            data={"top_threats": data},
            message="Top 10 règles de corrélation les plus déclenchées.",
        )


class DashboardGeoMapView(APIView):
    """
    GET /api/dashboard/geo-map/
    Agrégation des logs par pays avec count.
    """

    permission_classes = [IsAuthenticated]

    def get(self, request):
        from apps.logs.models import NormalizedLog

        now = timezone.now()
        last_24h = now - timedelta(hours=24)

        geo_data = (
            NormalizedLog.objects
            .filter(
                organization_id=request.user.organization_id,
                event_time__gte=last_24h,
                geo_country__isnull=False,
            )
            .values("geo_country")
            .annotate(
                total=Count("id"),
                failures=Count("id", filter=Q(outcome="failure")),
                successes=Count("id", filter=Q(outcome="success")),
            )
            .order_by("-total")
        )

        return success_response(
            data={
                "period": "24h",
                "countries": list(geo_data),
                "generated_at": now.isoformat(),
            },
            message="Distribution géographique des logs sur les 24 dernières heures.",
        )
