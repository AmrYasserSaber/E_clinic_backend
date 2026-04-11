from django.urls import path

from patients.views import PatientMeView

urlpatterns = [
    path("me/", PatientMeView.as_view(), name="patient-me"),
]
