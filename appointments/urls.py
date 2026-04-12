from django.urls import path

from appointments.views import (
    AppointmentConsultationCreateView,
    AppointmentCancelView,
    AppointmentCheckInView,
    AppointmentConfirmView,
    AppointmentDeclineView,
    AppointmentDetailView,
    AppointmentListCreateView,
	AvailableSlotsView,
    DoctorMyQueueView,
    DoctorMyScheduleView,
    AppointmentNoShowView,
    AppointmentRescheduleView,
)

urlpatterns = [
	path("doctors/me/schedule/", DoctorMyScheduleView.as_view(), name="doctor-me-schedule"),
	path("doctors/me/queue/", DoctorMyQueueView.as_view(), name="doctor-me-queue"),
	path("appointments/", AppointmentListCreateView.as_view(), name="appointments-list-create"),
	path("appointments/<int:pk>/", AppointmentDetailView.as_view(), name="appointments-detail"),
	path("appointments/<int:pk>/cancel/", AppointmentCancelView.as_view(), name="appointments-cancel"),
	path("appointments/<int:pk>/confirm/", AppointmentConfirmView.as_view(), name="appointments-confirm"),
	path("appointments/<int:pk>/decline/", AppointmentDeclineView.as_view(), name="appointments-decline"),
	path("appointments/<int:pk>/check-in/", AppointmentCheckInView.as_view(), name="appointments-check-in"),
	path("appointments/<int:pk>/no-show/", AppointmentNoShowView.as_view(), name="appointments-no-show"),
	path("appointments/<int:pk>/reschedule/", AppointmentRescheduleView.as_view(), name="appointments-reschedule"),
	path("appointments/<int:pk>/consultation/", AppointmentConsultationCreateView.as_view(), name="appointments-consultation"),
  path("slots/", AvailableSlotsView.as_view(), name="available-slots"),
]
