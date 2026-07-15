"""Générateur de rapport « Top menaces » — classement MITRE ATT&CK des TTPs observés."""
from datetime import timedelta

from django.db.models import Count
from django.utils import timezone
from reportlab.platypus import Paragraph, Spacer

from .base import BaseReportGenerator, make_table


class TopThreatsReportGenerator(BaseReportGenerator):
    FRAMEWORK = "MITRE"
    TITLE = "Top menaces détectées — classement MITRE ATT&CK"

    def collect_data(self) -> dict:
        from apps.alerts.models import Alert

        cutoff = timezone.now() - timedelta(days=self.period_days)
        alerts = Alert.objects.filter(
            organization_id=self.organization_id, created_at__gte=cutoff
        ).select_related("rule")

        by_tactic = list(
            alerts.exclude(rule__mitre_tactic__isnull=True)
            .exclude(rule__mitre_tactic="")
            .values("rule__mitre_tactic")
            .annotate(c=Count("id"))
            .order_by("-c")[:15]
        )
        by_technique = list(
            alerts.exclude(rule__mitre_technique__isnull=True)
            .exclude(rule__mitre_technique="")
            .values("rule__mitre_technique", "rule__name")
            .annotate(c=Count("id"))
            .order_by("-c")[:15]
        )
        top_titles = list(
            alerts.values("title").annotate(c=Count("id")).order_by("-c")[:10]
        )
        ml_alerts = alerts.filter(rule__isnull=True).count()

        return {
            "total_alerts": alerts.count(),
            "by_tactic": by_tactic,
            "by_technique": by_technique,
            "top_titles": top_titles,
            "ml_alerts": ml_alerts,
            "rule_alerts": alerts.exclude(rule__isnull=True).count(),
        }

    def build_elements(self, data: dict) -> list:
        s = self.styles
        elements = []

        elements.append(Paragraph("Résumé", s["H2"]))
        summary = [
            ["Indicateur", "Valeur"],
            ["Alertes totales", str(data["total_alerts"])],
            ["Détections par règle de corrélation", str(data["rule_alerts"])],
            ["Détections par modèle ML (anomalies)", str(data["ml_alerts"])],
        ]
        elements.append(make_table(summary, col_widths=[300, 100]))
        elements.append(Spacer(1, 12))

        elements.append(Paragraph("Tactiques MITRE ATT&CK observées", s["H2"]))
        if data["by_tactic"]:
            rows = [["Tactique", "Occurrences"]] + [
                [r["rule__mitre_tactic"], str(r["c"])] for r in data["by_tactic"]
            ]
            elements.append(make_table(rows, col_widths=[300, 100]))
        else:
            elements.append(Paragraph("Aucune tactique MITRE associée aux alertes de la période.", s["Body"]))
        elements.append(Spacer(1, 12))

        elements.append(Paragraph("Techniques MITRE ATT&CK observées", s["H2"]))
        if data["by_technique"]:
            rows = [["Technique", "Règle", "Occurrences"]] + [
                [r["rule__mitre_technique"], r["rule__name"] or "—", str(r["c"])]
                for r in data["by_technique"]
            ]
            elements.append(make_table(rows, col_widths=[130, 190, 80]))
        else:
            elements.append(Paragraph("Aucune technique MITRE associée aux alertes de la période.", s["Body"]))
        elements.append(Spacer(1, 12))

        elements.append(Paragraph("Top 10 types d'alertes", s["H2"]))
        if data["top_titles"]:
            rows = [["Titre", "Occurrences"]] + [
                [r["title"], str(r["c"])] for r in data["top_titles"]
            ]
            elements.append(make_table(rows, col_widths=[300, 100]))
        else:
            elements.append(Paragraph("Aucune alerte sur la période.", s["Body"]))

        return elements
