"""Générateur de rapport hebdomadaire SOC — synthèse alertes, tendances, top menaces."""
from datetime import timedelta

from django.db.models import Count
from django.db.models.functions import TruncDay
from django.utils import timezone
from reportlab.platypus import Paragraph, Spacer

from .base import BaseReportGenerator, make_table


class SOCWeeklyReportGenerator(BaseReportGenerator):
    FRAMEWORK = "SOC"
    TITLE = "Rapport hebdomadaire SOC — synthèse des alertes"

    def collect_data(self) -> dict:
        from apps.alerts.models import Alert
        from apps.logs.models import NormalizedLog

        cutoff = timezone.now() - timedelta(days=self.period_days)
        alerts = Alert.objects.filter(organization_id=self.organization_id, created_at__gte=cutoff)
        logs = NormalizedLog.objects.filter(organization_id=self.organization_id, indexed_at__gte=cutoff)

        by_severity = {row["severity"]: row["c"] for row in alerts.values("severity").annotate(c=Count("id"))}
        by_status = {row["status"]: row["c"] for row in alerts.values("status").annotate(c=Count("id"))}
        daily = list(
            alerts.annotate(day=TruncDay("created_at"))
            .values("day")
            .annotate(c=Count("id"))
            .order_by("day")
        )
        top_rules = list(
            alerts.exclude(rule__isnull=True)
            .values("rule__name")
            .annotate(c=Count("id"))
            .order_by("-c")[:10]
        )
        top_ips = list(
            logs.exclude(source_ip="").exclude(source_ip__isnull=True)
            .values("source_ip")
            .annotate(c=Count("id"))
            .order_by("-c")[:10]
        )

        return {
            "total_alerts": alerts.count(),
            "total_logs": logs.count(),
            "by_severity": by_severity,
            "by_status": by_status,
            "daily": daily,
            "top_rules": top_rules,
            "top_ips": top_ips,
            "false_positive_rate": round(
                by_status.get("false_positive", 0) / alerts.count() * 100, 1
            ) if alerts.count() else 0.0,
        }

    def build_elements(self, data: dict) -> list:
        s = self.styles
        elements = []

        elements.append(Paragraph("Résumé de la période", s["H2"]))
        summary = [
            ["Indicateur", "Valeur"],
            ["Logs ingérés", str(data["total_logs"])],
            ["Alertes générées", str(data["total_alerts"])],
            ["Critiques", str(data["by_severity"].get("critical", 0))],
            ["Élevées", str(data["by_severity"].get("high", 0))],
            ["Moyennes", str(data["by_severity"].get("medium", 0))],
            ["Faibles", str(data["by_severity"].get("low", 0))],
            ["Résolues", str(data["by_status"].get("resolved", 0))],
            ["Taux de faux positifs", f"{data['false_positive_rate']} %"],
        ]
        elements.append(make_table(summary, col_widths=[250, 150]))
        elements.append(Spacer(1, 12))

        elements.append(Paragraph("Volumétrie quotidienne des alertes", s["H2"]))
        if data["daily"]:
            rows = [["Jour", "Alertes"]] + [
                [d["day"].strftime("%d/%m/%Y"), str(d["c"])] for d in data["daily"]
            ]
            elements.append(make_table(rows, col_widths=[250, 150]))
        else:
            elements.append(Paragraph("Aucune alerte sur la période.", s["Body"]))
        elements.append(Spacer(1, 12))

        elements.append(Paragraph("Top 10 règles de corrélation déclenchées", s["H2"]))
        if data["top_rules"]:
            rows = [["Règle", "Occurrences"]] + [
                [r["rule__name"] or "—", str(r["c"])] for r in data["top_rules"]
            ]
            elements.append(make_table(rows, col_widths=[300, 100]))
        else:
            elements.append(Paragraph("Aucune règle déclenchée sur la période.", s["Body"]))
        elements.append(Spacer(1, 12))

        elements.append(Paragraph("Top 10 adresses IP sources", s["H2"]))
        if data["top_ips"]:
            rows = [["IP source", "Occurrences"]] + [
                [r["source_ip"], str(r["c"])] for r in data["top_ips"]
            ]
            elements.append(make_table(rows, col_widths=[300, 100]))
        else:
            elements.append(Paragraph("Aucune IP source enregistrée sur la période.", s["Body"]))

        return elements
