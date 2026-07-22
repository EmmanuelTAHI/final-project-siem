from django.urls import path
from rest_framework.routers import DefaultRouter

from .views import (
    AvailableFrameworksView,
    ComplianceCoverageView,
    ComplianceReportView,
    ReportExportView,
    ReportGenerateView,
    ReportHistoryViewSet,
)

router = DefaultRouter()
router.register("history", ReportHistoryViewSet, basename="report-history")

urlpatterns = [
    path("compliance/", ComplianceReportView.as_view(), name="compliance-report"),
    path("compliance-coverage/", ComplianceCoverageView.as_view(), name="compliance-coverage"),
    path("frameworks/", AvailableFrameworksView.as_view(), name="available-frameworks"),
    path("generate/", ReportGenerateView.as_view(), name="report-generate"),
    path("export/", ReportExportView.as_view(), name="report-export"),
] + router.urls
