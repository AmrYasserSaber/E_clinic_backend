from django.urls import path

from appointments.views import AppointmentBookingView

urlpatterns = [
	path("appointments/", AppointmentBookingView.as_view(), name="appointments-book"),
]
