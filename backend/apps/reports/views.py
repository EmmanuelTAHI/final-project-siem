"""
API Rapports — génération PDF à la demande (compliance, SOC, activité) +
export brut CSV/JSON + historique des rapports générés.
"""
import csv
import io
import json
from datetime import datetime

from django.core.files.base import ContentFile
from django.http import HttpResponse
from django.utils import timezone
from rest_framework import status
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework.viewsets import ReadOnlyModelViewSet

from utils.permissions import IsAnalyst
from utils.response import error_response, success_response
from utils.tenant import OrganizationFilterBackend

from .compliance_catalog import COMPLIANCE_CATALOG, build_compliance_coverage
from .models import GeneratedReport
from .serializers import GeneratedReportSerializer

# ─── Générateurs PDF disponibles ────────────────────────────────────────────

GENERATORS = {
    "pci_dss": "apps.reports.generators.pci_dss.PCIDSSReportGenerator",
    "gdpr": "apps.reports.generators.gdpr.GDPRReportGenerator",
    "iso27001": "apps.reports.generators.iso27001.ISO27001ReportGenerator",
    "soc_weekly": "apps.reports.generators.soc_weekly.SOCWeeklyReportGenerator",
    "top_threats": "apps.reports.generators.top_threats.TopThreatsReportGenerator",
    "user_activity": "apps.reports.generators.user_activity.UserActivityReportGenerator",
}

REPORT_LABELS = {
    "pci_dss": "PCI DSS v4.0",
    "gdpr": "RGPD",
    "iso27001": "ISO 27001:2022",
    "soc_weekly": "Rapport hebdomadaire SOC",
    "top_threats": "Top menaces détectées",
    "user_activity": "Activité utilisateurs",
}

FRAMEWORK_LABELS = {
    "pci_dss": "PCI DSS v4.0",
    "gdpr": "RGPD",
    "iso27001": "ISO 27001:2022",
}

# Sources de logs réelles (doit rester aligné sur RawLog.SOURCE_TYPE_CHOICES).
VALID_SOURCES = {"microsoft365", "google_workspace", "wazuh", "syslog", "agent"}


def _load_generator(report_type: str):
    module_path, class_name = GENERATORS[report_type].rsplit(".", 1)
    import importlib
    module = importlib.import_module(module_path)
    return getattr(module, class_name)


def _save_history(request, report_type, label, fmt, period_days, content: bytes, ext: str) -> GeneratedReport:
    filename = f"{report_type}_{datetime.utcnow().strftime('%Y%m%d_%H%M%S')}.{ext}"
    report = GeneratedReport(
        organization_id=request.user.organization_id,
        requested_by=request.user,
        report_type=report_type,
        label=label,
        format=fmt,
        period_days=period_days,
        file_size=len(content),
    )
    report.file.save(filename, ContentFile(content), save=True)
    return report


class ComplianceReportView(APIView):
    """
    GET /api/reports/compliance/?framework=pci_dss&period=30
    Retourne un PDF téléchargeable (conservé pour compatibilité).
    """
    permission_classes = [IsAnalyst]

    def get(self, request):
        framework = request.query_params.get("framework", "pci_dss").lower()
        period = int(request.query_params.get("period", 30))

        if framework not in FRAMEWORK_LABELS:
            return Response(
                {"error": f"Framework inconnu. Valeurs acceptées: {list(FRAMEWORK_LABELS.keys())}"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        period = max(7, min(period, 365))
        generator_class = _load_generator(framework)

        try:
            generator = generator_class(period_days=period, organization_id=request.user.organization_id)
            pdf_bytes = generator.generate()
        except Exception as exc:
            return Response(
                {"error": f"Erreur génération PDF: {str(exc)}"},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )

        _save_history(request, framework, FRAMEWORK_LABELS[framework], "pdf", period, pdf_bytes, "pdf")

        filename = f"Argus_{framework.upper()}_{datetime.utcnow().strftime('%Y%m%d_%H%M')}.pdf"
        response = HttpResponse(pdf_bytes, content_type="application/pdf")
        response["Content-Disposition"] = f'attachment; filename="{filename}"'
        response["Content-Length"] = len(pdf_bytes)
        return response


class AvailableFrameworksView(APIView):
    """GET /api/reports/frameworks/ — liste les frameworks disponibles."""
    permission_classes = [IsAnalyst]

    def get(self, request):
        return Response([
            {"id": k, "label": v, "description": _get_description(k)}
            for k, v in FRAMEWORK_LABELS.items()
        ])


def _get_description(framework: str) -> str:
    descs = {
        "pci_dss": "Payment Card Industry Data Security Standard v4.0",
        "gdpr": "Règlement Général sur la Protection des Données (UE 2016/679)",
        "iso27001": "Système de Management de la Sécurité de l'Information — ISO/IEC 27001:2022",
    }
    return descs.get(framework, "")


class ReportGenerateView(APIView):
    """
    GET /api/reports/generate/?type=soc_weekly&period=7
    Génère un rapport PDF (compliance, SOC, top menaces ou activité utilisateurs),
    l'enregistre dans l'historique de l'organisation et le retourne en téléchargement.
    """
    permission_classes = [IsAnalyst]

    def get(self, request):
        report_type = request.query_params.get("type", "").lower()
        period = int(request.query_params.get("period", 30))

        if report_type not in GENERATORS:
            return error_response(
                message=f"Type de rapport inconnu. Valeurs acceptées: {list(GENERATORS.keys())}",
                http_status=status.HTTP_400_BAD_REQUEST,
            )

        period = max(1, min(period, 365))
        generator_class = _load_generator(report_type)

        try:
            generator = generator_class(period_days=period, organization_id=request.user.organization_id)
            pdf_bytes = generator.generate()
        except Exception as exc:
            return error_response(
                message=f"Erreur génération du rapport: {str(exc)}",
                http_status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )

        label = REPORT_LABELS[report_type]
        _save_history(request, report_type, label, "pdf", period, pdf_bytes, "pdf")

        filename = f"Argus_{report_type}_{datetime.utcnow().strftime('%Y%m%d_%H%M')}.pdf"
        response = HttpResponse(pdf_bytes, content_type="application/pdf")
        response["Content-Disposition"] = f'attachment; filename="{filename}"'
        response["Content-Length"] = len(pdf_bytes)
        return response


class ReportExportView(APIView):
    """
    GET /api/reports/export/?sources=microsoft365,wazuh&period=7&format=csv
    Export « rapport personnalisé » : logs normalisés filtrés par sources et
    période, au format csv, json ou pdf (résumé imprimable).
    """
    permission_classes = [IsAnalyst]

    def perform_content_negotiation(self, request, force=False):
        # Cette vue construit sa propre HttpResponse (jamais un Response DRF
        # rendu par un renderer négocié) : le renderer choisi ici n'est donc
        # jamais réellement utilisé. On bypass la négociation par défaut de
        # DRF car elle lit aussi le paramètre de requête "format" (réservé,
        # `URL_FORMAT_OVERRIDE`) et levait un Http404 dès que sa valeur ne
        # correspondait à aucun renderer déclaré (ex: ?format=csv ou
        # ?format=pdf, alors que seul JSONRenderer est enregistré) — avant
        # même que le paramètre "format" propre à cette vue (csv/json/pdf)
        # ne soit lu ci-dessous.
        renderer = self.get_renderers()[0]
        return renderer, renderer.media_type

    def get(self, request):
        from apps.logs.models import NormalizedLog

        fmt = request.query_params.get("format", "csv").lower()
        period = max(1, min(int(request.query_params.get("period", 7)), 365))
        raw_sources = [s.strip() for s in request.query_params.get("sources", "").split(",") if s.strip()]
        sources = [s for s in raw_sources if s in VALID_SOURCES] or list(VALID_SOURCES)

        if fmt not in ("csv", "json", "pdf"):
            return error_response(
                message="Format inconnu. Valeurs acceptées: csv, json, pdf.",
                http_status=status.HTTP_400_BAD_REQUEST,
            )

        cutoff = timezone.now() - timezone.timedelta(days=period)
        logs = (
            NormalizedLog.objects
            .filter(organization_id=request.user.organization_id, event_time__gte=cutoff, source_type__in=sources)
            .order_by("-event_time")[:5000]
        )

        if fmt == "csv":
            buffer = io.StringIO()
            writer = csv.writer(buffer)
            writer.writerow(["event_time", "source_type", "action", "outcome", "severity", "user_email", "source_ip", "resource"])
            for log in logs:
                writer.writerow([
                    log.event_time.isoformat(), log.source_type, log.action, log.outcome,
                    log.severity, log.user_email or "", log.source_ip or "", log.resource or "",
                ])
            content = buffer.getvalue().encode("utf-8")
            content_type = "text/csv"
            ext = "csv"
        elif fmt == "json":
            payload = [
                {
                    "event_time": log.event_time.isoformat(),
                    "source_type": log.source_type,
                    "action": log.action,
                    "outcome": log.outcome,
                    "severity": log.severity,
                    "user_email": log.user_email,
                    "source_ip": log.source_ip,
                    "resource": log.resource,
                }
                for log in logs
            ]
            content = json.dumps(payload, ensure_ascii=False, indent=2).encode("utf-8")
            content_type = "application/json"
            ext = "json"
        else:
            from .generators.custom import CustomActivityReportGenerator
            generator = CustomActivityReportGenerator(
                period_days=period, organization_id=request.user.organization_id, sources=sources
            )
            content = generator.generate()
            content_type = "application/pdf"
            ext = "pdf"

        _save_history(request, "custom", "Rapport personnalisé", fmt, period, content, ext)

        filename = f"Argus_custom_{datetime.utcnow().strftime('%Y%m%d_%H%M')}.{ext}"
        response = HttpResponse(content, content_type=content_type)
        response["Content-Disposition"] = f'attachment; filename="{filename}"'
        response["Content-Length"] = len(content)
        return response


class ComplianceCoverageView(APIView):
    """
    GET /api/reports/compliance-coverage/?framework=iso27001
    Matrice de couverture EN CONTINU (pas un PDF ponctuel) : quels contrôles
    sont couverts par au moins une règle de détection active de
    l'organisation, dès maintenant. Complète les rapports PDF à la demande
    par une vue "toujours à jour" de la posture de conformité opérationnelle.
    """
    permission_classes = [IsAnalyst]

    def get(self, request):
        framework = request.query_params.get("framework", "iso27001").lower()
        if framework not in COMPLIANCE_CATALOG:
            return Response(
                {"error": f"Framework inconnu. Valeurs acceptées: {list(COMPLIANCE_CATALOG.keys())}"},
                status=status.HTTP_400_BAD_REQUEST,
            )
        coverage = build_compliance_coverage(request.user.organization_id, framework)
        return Response(coverage)


class ReportHistoryViewSet(ReadOnlyModelViewSet):
    """
    GET /api/reports/history/ — rapports générés par l'organisation (les plus récents en premier).
    GET /api/reports/history/{id}/download/ — retélécharge un rapport déjà généré.
    """
    queryset = GeneratedReport.objects.select_related("requested_by").all()
    serializer_class = GeneratedReportSerializer
    permission_classes = [IsAnalyst]
    filter_backends = [OrganizationFilterBackend]

    def list(self, request, *args, **kwargs):
        queryset = self.filter_queryset(self.get_queryset())[:50]
        serializer = self.get_serializer(queryset, many=True)
        return success_response(data=serializer.data, message="Historique des rapports.")

    @action(detail=True, methods=["get"], url_path="download")
    def download(self, request, pk=None):
        report = self.get_object()
        content_types = {"pdf": "application/pdf", "csv": "text/csv", "json": "application/json"}
        response = HttpResponse(report.file.read(), content_type=content_types.get(report.format, "application/octet-stream"))
        response["Content-Disposition"] = f'attachment; filename="{report.file.name.rsplit("/", 1)[-1]}"'
        return response
