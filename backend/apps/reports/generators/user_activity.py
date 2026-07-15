"""Générateur de rapport « Activité utilisateurs » — connexions, élévations, anomalies ML."""
from datetime import timedelta

from django.db.models import Count, Q
from django.utils import timezone
from reportlab.platypus import Paragraph, Spacer

from .base import BaseReportGenerator, make_table

PRIVILEGE_ACTIONS = ["privilege_change", "role_assigned", "admin_role_assigned"]


class UserActivityReportGenerator(BaseReportGenerator):
    FRAMEWORK = "IAM"
    TITLE = "Activité utilisateurs — connexions, élévations et anomalies"

    def collect_data(self) -> dict:
        from apps.alerts.models import Alert
        from apps.logs.models import NormalizedLog

        cutoff = timezone.now() - timedelta(days=self.period_days)
        logs = NormalizedLog.objects.filter(organization_id=self.organization_id, event_time__gte=cutoff)
        alerts = Alert.objects.filter(organization_id=self.organization_id, created_at__gte=cutoff)

        top_active = list(
            logs.exclude(user_email="").exclude(user_email__isnull=True)
            .values("user_email")
            .annotate(c=Count("id"))
            .order_by("-c")[:10]
        )
        top_failed = list(
            logs.filter(action="login_failure")
            .exclude(user_email="").exclude(user_email__isnull=True)
            .values("user_email")
            .annotate(c=Count("id"))
            .order_by("-c")[:10]
        )
        privilege_events = list(
            logs.filter(action__in=PRIVILEGE_ACTIONS)
            .values("user_email", "action", "event_time")
            .order_by("-event_time")[:20]
        )
        ml_anomalies = list(
            alerts.filter(rule__isnull=True).order_by("-created_at")[:15]
        )

        return {
            "total_logins_success": logs.filter(action="login_success").count(),
            "total_logins_failure": logs.filter(action="login_failure").count(),
            "unique_users": logs.exclude(user_email="").values("user_email").distinct().count(),
            "top_active": top_active,
            "top_failed": top_failed,
            "privilege_events": privilege_events,
            "ml_anomalies": ml_anomalies,
        }

    def build_elements(self, data: dict) -> list:
        s = self.styles
        elements = []

        elements.append(Paragraph("Résumé des connexions", s["H2"]))
        summary = [
            ["Indicateur", "Valeur"],
            ["Utilisateurs actifs", str(data["unique_users"])],
            ["Connexions réussies", str(data["total_logins_success"])],
            ["Connexions échouées", str(data["total_logins_failure"])],
        ]
        elements.append(make_table(summary, col_widths=[250, 150]))
        elements.append(Spacer(1, 12))

        elements.append(Paragraph("Top 10 utilisateurs les plus actifs", s["H2"]))
        if data["top_active"]:
            rows = [["Utilisateur", "Évènements"]] + [
                [r["user_email"], str(r["c"])] for r in data["top_active"]
            ]
            elements.append(make_table(rows, col_widths=[300, 100]))
        else:
            elements.append(Paragraph("Aucune activité utilisateur sur la période.", s["Body"]))
        elements.append(Spacer(1, 12))

        elements.append(Paragraph("Top 10 échecs de connexion par utilisateur", s["H2"]))
        if data["top_failed"]:
            rows = [["Utilisateur", "Échecs"]] + [
                [r["user_email"], str(r["c"])] for r in data["top_failed"]
            ]
            elements.append(make_table(rows, col_widths=[300, 100]))
        else:
            elements.append(Paragraph("Aucun échec de connexion sur la période.", s["Body"]))
        elements.append(Spacer(1, 12))

        elements.append(Paragraph("Élévations de privilèges", s["H2"]))
        if data["privilege_events"]:
            rows = [["Utilisateur", "Action", "Date"]] + [
                [r["user_email"] or "—", r["action"], r["event_time"].strftime("%d/%m/%Y %H:%M")]
                for r in data["privilege_events"]
            ]
            elements.append(make_table(rows, col_widths=[180, 140, 130]))
        else:
            elements.append(Paragraph("Aucune élévation de privilège détectée sur la période.", s["Body"]))
        elements.append(Spacer(1, 12))

        elements.append(Paragraph("Anomalies détectées par le modèle ML", s["H2"]))
        if data["ml_anomalies"]:
            rows = [["Titre", "Sévérité", "Date"]] + [
                [a.title, a.get_severity_display(), a.created_at.strftime("%d/%m/%Y %H:%M")]
                for a in data["ml_anomalies"]
            ]
            elements.append(make_table(rows, col_widths=[240, 90, 120]))
        else:
            elements.append(Paragraph("Aucune anomalie ML détectée sur la période.", s["Body"]))

        return elements
