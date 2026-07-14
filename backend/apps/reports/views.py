"""
API Rapports de conformité — génération PDF à la demande.
"""
from django.http import HttpResponse
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status

from utils.permissions import IsAnalyst

GENERATORS = {
    "pci_dss": "apps.reports.generators.pci_dss.PCIDSSReportGenerator",
    "gdpr": "apps.reports.generators.gdpr.GDPRReportGenerator",
    "iso27001": "apps.reports.generators.iso27001.ISO27001ReportGenerator",
}

FRAMEWORK_LABELS = {
    "pci_dss": "PCI DSS v4.0",
    "gdpr": "RGPD",
    "iso27001": "ISO 27001:2022",
}


class ComplianceReportView(APIView):
    """
    GET /api/reports/compliance/?framework=pci_dss&period=30
    Retourne un PDF téléchargeable.
    """
    permission_classes = [IsAnalyst]

    def get(self, request):
        framework = request.query_params.get("framework", "pci_dss").lower()
        period = int(request.query_params.get("period", 30))

        if framework not in GENERATORS:
            return Response(
                {"error": f"Framework inconnu. Valeurs acceptées: {list(GENERATORS.keys())}"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        period = max(7, min(period, 365))

        import importlib
        module_path, class_name = GENERATORS[framework].rsplit(".", 1)
        module = importlib.import_module(module_path)
        generator_class = getattr(module, class_name)

        try:
            generator = generator_class(
                period_days=period, organization_id=request.user.organization_id
            )
            pdf_bytes = generator.generate()
        except Exception as exc:
            return Response(
                {"error": f"Erreur génération PDF: {str(exc)}"},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )

        from datetime import datetime
        filename = f"LogPlus_{framework.upper()}_{datetime.utcnow().strftime('%Y%m%d_%H%M')}.pdf"

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
