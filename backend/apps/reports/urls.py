from django.urls import path
from .views import AvailableFrameworksView, ComplianceReportView

urlpatterns = [
    path("compliance/", ComplianceReportView.as_view(), name="compliance-report"),
    path("frameworks/", AvailableFrameworksView.as_view(), name="available-frameworks"),
]
