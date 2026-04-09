from django.urls import path
from .views import AppointmentExportCsvView

urlpatterns = [
    path("appointments/export/", AppointmentExportCsvView.as_view(), name="appointments-export"),
]