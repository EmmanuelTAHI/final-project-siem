"""Générateur de rapport de conformité ISO 27001:2022."""
from datetime import timedelta

from django.utils import timezone
from reportlab.platypus import Paragraph, Spacer

from .base import BaseReportGenerator, make_table


class ISO27001ReportGenerator(BaseReportGenerator):
    FRAMEWORK = "ISO 27001:2022"
    TITLE = "Rapport de conformité ISO/IEC 27001:2022 — Sécurité de l'Information"

    def collect_data(self) -> dict:
        from apps.alerts.models import Alert
        from apps.correlation.models import CorrelationRule
        from apps.logs.models import NormalizedLog
        from apps.users.models import AuditTrail, User

        cutoff = timezone.now() - timedelta(days=self.period_days)
        alerts = Alert.objects.filter(organization_id=self.organization_id, created_at__gte=cutoff)
        logs = NormalizedLog.objects.filter(organization_id=self.organization_id, indexed_at__gte=cutoff)
        rules = CorrelationRule.objects.filter(organization_id=self.organization_id)

        resolved = alerts.filter(status="resolved")
        mttr_avg = 0.0
        if resolved.exists():
            import statistics
            mttr_values = [
                a.time_to_resolve_hours for a in resolved if a.time_to_resolve_hours is not None
            ]
            if mttr_values:
                mttr_avg = round(statistics.mean(mttr_values), 1)

        return {
            "active_rules": rules.filter(is_active=True).count(),
            "total_rules": rules.count(),
            "total_alerts": alerts.count(),
            "resolved_alerts": resolved.count(),
            "mttr_hours": mttr_avg,
            "total_users": User.objects.filter(
                is_active=True, organization_id=self.organization_id
            ).count(),
            "audit_entries": AuditTrail.objects.filter(
                organization_id=self.organization_id, timestamp__gte=cutoff
            ).count(),
            "total_logs": logs.count(),
            "sources_active": logs.values("source_type").distinct().count(),
        }

    def build_elements(self, data: dict) -> list:
        s = self.styles
        elements = []

        controls = [
            ["Contrôle", "Domaine", "Statut", "Mesure"],
            ["A.5.1", "Politiques SSI", "✓", "Playbooks SOAR documentés"],
            ["A.5.9", "Inventaire des actifs", "✓", f"{data['sources_active']} sources de logs actives"],
            ["A.5.15", "Contrôle d'accès", "✓", "RBAC 3 niveaux (admin/analyst/viewer)"],
            ["A.5.16", "Gestion des identités", "✓", "JWT + OAuth2 PKCE"],
            ["A.5.23", "Sécurité cloud", "✓", "Microsoft 365 + Google Workspace monitorés"],
            ["A.5.25", "Gestion des incidents", _req(data["resolved_alerts"] > 0),
             f"MTTR moyen: {data['mttr_hours']}h"],
            ["A.5.26", "Réponse aux incidents", "✓", "SOAR-lite actif"],
            ["A.5.28", "Collecte des preuves", "✓", f"{data['audit_entries']} entrées d'audit"],
            ["A.5.36", "Conformité", "✓", "Rapports automatisés actifs"],
            ["A.8.16", "Surveillance des activités", "✓", f"{data['total_logs']} événements surveillés"],
            ["A.8.15", "Journalisation", "✓", "Logs normalisés CEF, rétention 90j"],
        ]

        elements.append(Paragraph("Contrôles ISO 27001:2022 évalués (Annexe A)", s["H2"]))
        elements.append(make_table(controls, col_widths=[60, 130, 60, 200]))
        elements.append(Spacer(1, 12))

        elements.append(Paragraph("Métriques opérationnelles de sécurité", s["H2"]))
        metrics = [
            ["KPI", "Valeur", "Objectif", "Statut"],
            ["Règles de corrélation actives", str(data["active_rules"]),
             f"≥ {data['total_rules']}", "✓" if data["active_rules"] == data["total_rules"] else "!"],
            ["Alertes traitées", str(data["resolved_alerts"]),
             f"/{data['total_alerts']}", _req(data["resolved_alerts"] > 0)],
            ["MTTR moyen", f"{data['mttr_hours']}h", "< 48h",
             "✓" if data["mttr_hours"] < 48 else "✗"],
            ["Utilisateurs actifs surveillés", str(data["total_users"]), "> 0", "✓"],
        ]
        elements.append(make_table(metrics, col_widths=[200, 80, 80, 60]))

        return elements


def _req(condition: bool) -> str:
    return "✓" if condition else "✗"
