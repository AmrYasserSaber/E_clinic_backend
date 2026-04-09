from django.urls import path

from .views import (
    AnalyticsByDoctorView,
    AnalyticsNoShowRateView,
    AnalyticsPeakHoursView,
    AnalyticsSummaryView,
)

urlpatterns = [
    path("analytics/", AnalyticsSummaryView.as_view(), name="analytics-summary"),
    path("analytics/peak-hours/", AnalyticsPeakHoursView.as_view(), name="analytics-peak-hours"),
    path("analytics/by-doctor/", AnalyticsByDoctorView.as_view(), name="analytics-by-doctor"),
    path("analytics/no-show-rate/", AnalyticsNoShowRateView.as_view(), name="analytics-no-show-rate"),
]