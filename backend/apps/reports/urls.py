from django.urls import path
from rest_framework.routers import DefaultRouter

from .views import (
    AvailableFrameworksView,
    ComplianceReportView,
    ReportExportView,
    ReportGenerateView,
    ReportHistoryViewSet,
)

router = DefaultRouter()
router.register("history", ReportHistoryViewSet, basename="report-history")

urlpatterns = [
    path("compliance/", ComplianceReportView.as_view(), name="compliance-report"),
    path("frameworks/", AvailableFrameworksView.as_view(), name="available-frameworks"),
    path("generate/", ReportGenerateView.as_view(), name="report-generate"),
    path("export/", ReportExportView.as_view(), name="report-export"),
] + router.urls
