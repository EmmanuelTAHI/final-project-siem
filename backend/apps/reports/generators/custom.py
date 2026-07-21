"""Générateur PDF pour le rapport personnalisé (sources sélectionnées par l'utilisateur)."""
from datetime import timedelta

from django.db.models import Count
from django.utils import timezone
from reportlab.platypus import Paragraph, Spacer

from .base import BaseReportGenerator, make_table

SOURCE_LABELS = {
    "microsoft365": "Microsoft 365",
    "google_workspace": "Google Workspace",
    "wazuh": "Wazuh",
    "syslog": "Syslog",
    "agent": "Agent Argus",
}


class CustomActivityReportGenerator(BaseReportGenerator):
    FRAMEWORK = "CUSTOM"
    TITLE = "Rapport personnalisé — activité par source"

    def __init__(self, period_days: int, organization_id, sources: list[str]):
        super().__init__(period_days=period_days, organization_id=organization_id)
        self.sources = sources

    def collect_data(self) -> dict:
        from apps.logs.models import NormalizedLog

        cutoff = timezone.now() - timedelta(days=self.period_days)
        logs = NormalizedLog.objects.filter(
            organization_id=self.organization_id, event_time__gte=cutoff, source_type__in=self.sources
        )

        by_source = list(logs.values("source_type").annotate(c=Count("id")).order_by("-c"))
        by_severity = list(logs.values("severity").annotate(c=Count("id")).order_by("-c"))
        by_action = list(logs.values("action").annotate(c=Count("id")).order_by("-c")[:15])

        return {
            "total": logs.count(),
            "by_source": by_source,
            "by_severity": by_severity,
            "by_action": by_action,
        }

    def build_elements(self, data: dict) -> list:
        s = self.styles
        elements = []

        elements.append(Paragraph("Sources incluses", s["H2"]))
        elements.append(Paragraph(
            ", ".join(SOURCE_LABELS.get(src, src) for src in self.sources) or "Aucune",
            s["Body"],
        ))
        elements.append(Spacer(1, 12))

        elements.append(Paragraph("Volumétrie par source", s["H2"]))
        if data["by_source"]:
            rows = [["Source", "Évènements"]] + [
                [SOURCE_LABELS.get(r["source_type"], r["source_type"]), str(r["c"])]
                for r in data["by_source"]
            ]
            elements.append(make_table(rows, col_widths=[250, 150]))
        else:
            elements.append(Paragraph("Aucun évènement pour les sources sélectionnées.", s["Body"]))
        elements.append(Spacer(1, 12))

        elements.append(Paragraph("Répartition par sévérité", s["H2"]))
        if data["by_severity"]:
            rows = [["Sévérité", "Évènements"]] + [
                [r["severity"], str(r["c"])] for r in data["by_severity"]
            ]
            elements.append(make_table(rows, col_widths=[250, 150]))
        else:
            elements.append(Paragraph("Aucune donnée.", s["Body"]))
        elements.append(Spacer(1, 12))

        elements.append(Paragraph("Top 15 actions observées", s["H2"]))
        if data["by_action"]:
            rows = [["Action", "Occurrences"]] + [
                [r["action"], str(r["c"])] for r in data["by_action"]
            ]
            elements.append(make_table(rows, col_widths=[250, 150]))
        else:
            elements.append(Paragraph("Aucune donnée.", s["Body"]))

        return elements
