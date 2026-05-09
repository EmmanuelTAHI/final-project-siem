from django.urls import path

from .views import (
    DashboardGeoMapView,
    DashboardSummaryView,
    DashboardTimelineView,
    DashboardTopThreatsView,
)

urlpatterns = [
    path("summary/", DashboardSummaryView.as_view(), name="dashboard-summary"),
    path("timeline/", DashboardTimelineView.as_view(), name="dashboard-timeline"),
    path("top-threats/", DashboardTopThreatsView.as_view(), name="dashboard-top-threats"),
    path("geo-map/", DashboardGeoMapView.as_view(), name="dashboard-geo-map"),
]
