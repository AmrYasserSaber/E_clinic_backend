from django.contrib import admin

from appointments.models import Appointment


@admin.register(Appointment)
class AppointmentAdmin(admin.ModelAdmin):
    list_display = (
        "id",
        "patient",
        "doctor",
        "date",
        "time",
        "session_duration",
        "status",
        "check_in_time",
        "updated_at",
    )
    list_filter = ("status", "date", "doctor")
    search_fields = (
        "patient__email",
        "patient__first_name",
        "patient__last_name",
        "doctor__email",
        "doctor__first_name",
        "doctor__last_name",
    )
