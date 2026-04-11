from django.contrib import admin

from .models import DoctorSchedule, ScheduleException


@admin.register(DoctorSchedule)
class DoctorScheduleAdmin(admin.ModelAdmin):
    list_display = (
        "doctor",
        "day_of_week",
        "start_time",
        "end_time",
        "session_duration_minutes",
        "buffer_minutes",
    )
    list_filter = ("day_of_week", "doctor")
    search_fields = ("doctor__email", "doctor__first_name", "doctor__last_name")


@admin.register(ScheduleException)
class ScheduleExceptionAdmin(admin.ModelAdmin):
    list_display = (
        "doctor",
        "exception_type",
        "start_date",
        "end_date",
        "custom_start_time",
        "custom_end_time",
    )
    list_filter = ("exception_type", "start_date", "doctor")
    search_fields = ("doctor__email", "doctor__first_name", "doctor__last_name", "reason")
