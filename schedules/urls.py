from django.urls import path

from .views import (
    DoctorScheduleDayUpdateView,
    DoctorScheduleExceptionDeleteView,
    DoctorScheduleExceptionListCreateView,
    DoctorScheduleListUpsertView,
)

urlpatterns = [
    path("doctors/<int:id>/schedule/", DoctorScheduleListUpsertView.as_view(), name="doctor-schedule-list-upsert"),
    path("doctors/<int:id>/schedule/<int:day>/", DoctorScheduleDayUpdateView.as_view(), name="doctor-schedule-day-update"),
    path(
        "doctors/<int:id>/schedule/exceptions/",
        DoctorScheduleExceptionListCreateView.as_view(),
        name="doctor-schedule-exceptions-list-create",
    ),
    path(
        "doctors/<int:id>/schedule/exceptions/<int:exception_id>/",
        DoctorScheduleExceptionDeleteView.as_view(),
        name="doctor-schedule-exception-delete",
    ),
]
