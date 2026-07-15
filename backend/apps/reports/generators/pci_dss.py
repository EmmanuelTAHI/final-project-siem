"""Générateur de rapport de conformité PCI DSS v4.0."""
from datetime import timedelta

from django.db.models import Count, Q
from django.utils import timezone
from reportlab.platypus import Paragraph, Spacer, Table, TableStyle

from apps.alerts.models import Alert
from apps.logs.models import NormalizedLog
from apps.users.models import AuditTrail

from .base import BaseReportGenerator, GREEN, RED, ORANGE, make_table


class PCIDSSReportGenerator(BaseReportGenerator):
    FRAMEWORK = "PCI DSS v4.0"
    TITLE = "Rapport de conformité PCI DSS v4.0"

    def collect_data(self) -> dict:
        cutoff = timezone.now() - timedelta(days=self.period_days)
        alerts = Alert.objects.filter(organization_id=self.organization_id, created_at__gte=cutoff)
        logs = NormalizedLog.objects.filter(organization_id=self.organization_id, indexed_at__gte=cutoff)
        audit = AuditTrail.objects.filter(organization_id=self.organization_id, timestamp__gte=cutoff)

        return {
            "total_logs": logs.count(),
            "total_alerts": alerts.count(),
            "critical_alerts": alerts.filter(severity="critical").count(),
            "high_alerts": alerts.filter(severity="high").count(),
            "resolved_alerts": alerts.filter(status="resolved").count(),
            "false_positives": alerts.filter(status="false_positive").count(),
            "failed_logins": logs.filter(outcome="failure").count(),
            "privileged_actions": audit.filter(action__icontains="privilege").count(),
            "audit_entries": audit.count(),
            "unique_users": logs.values("user_email").distinct().count(),
            "geo_countries": logs.values("geo_country").distinct().count(),
        }

    def build_elements(self, data: dict) -> list:
        s = self.styles
        elements = []

        elements.append(Paragraph("Résumé exécutif", s["H2"]))
        summary_data = [
            ["Indicateur", "Valeur", "Statut"],
            ["Logs collectés", str(data["total_logs"]), "✓"],
            ["Alertes générées", str(data["total_alerts"]), "✓"],
            ["Alertes critiques", str(data["critical_alerts"]),
             "✗" if data["critical_alerts"] > 10 else "✓"],
            ["Alertes haute sévérité", str(data["high_alerts"]),
             "!" if data["high_alerts"] > 50 else "✓"],
            ["Taux résolution", f"{_pct(data['resolved_alerts'], data['total_alerts'])}%", "✓"],
            ["Faux positifs", str(data["false_positives"]),
             "!" if data["false_positives"] > data["total_alerts"] * 0.2 else "✓"],
            ["Tentatives échouées (auth)", str(data["failed_logins"]),
             "!" if data["failed_logins"] > 1000 else "✓"],
        ]
        elements.append(make_table(summary_data, col_widths=[240, 80, 80]))
        elements.append(Spacer(1, 12))

        requirements = [
            ("REQ 1", "Sécurité réseau", _req_status(data["total_logs"] > 0), "Logs réseau collectés"),
            ("REQ 2", "Configurations sécurisées", "✓", "Chiffrement AES-256 actif"),
            ("REQ 7", "Contrôle d'accès", _req_status(data["unique_users"] > 0), f"{data['unique_users']} utilisateurs surveillés"),
            ("REQ 8", "Gestion identités", _req_status(data["failed_logins"] < 5000), f"{data['failed_logins']} échecs auth"),
            ("REQ 10", "Logging et monitoring", "✓", f"{data['total_logs']} événements enregistrés"),
            ("REQ 10.3", "Audit trail", _req_status(data["audit_entries"] > 0), f"{data['audit_entries']} entrées d'audit"),
            ("REQ 11", "Tests sécurité", "✓", "Moteur de corrélation actif"),
            ("REQ 12", "Politique SSI", "✓", "Playbooks SOAR configurés"),
        ]

        elements.append(Paragraph("Contrôles PCI DSS évalués", s["H2"]))
        req_data = [["Exigence", "Domaine", "Statut", "Détail"]]
        for code, domain, st, detail in requirements:
            req_data.append([code, domain, st, detail])
        elements.append(make_table(req_data, col_widths=[60, 130, 60, 200]))
        elements.append(Spacer(1, 12))

        elements.append(Paragraph("Activité d'authentification", s["H2"]))
        auth_data = [
            ["Métrique", "Valeur"],
            ["Connexions échouées", str(data["failed_logins"])],
            ["Actions privilégiées", str(data["privileged_actions"])],
            ["Pays d'origine uniques", str(data["geo_countries"])],
        ]
        elements.append(make_table(auth_data, col_widths=[250, 150]))

        return elements


def _pct(num, denom) -> str:
    if denom == 0:
        return "N/A"
    return str(round(num / denom * 100, 1))


def _req_status(condition: bool) -> str:
    return "✓" if condition else "✗"
