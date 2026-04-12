from django.contrib import admin
from appointments.models import (
    Appointment,
    AppointmentAuditLog,
    ConsultationRecord,
    PrescriptionItem,
    RescheduleHistory,
)

@admin.register(Appointment)
class AppointmentAdmin(admin.ModelAdmin):
    list_display = (
        "id",
        "patient",
        "doctor",
        "appointment_date",
        "appointment_time",
        "session_duration_minutes",
        "status",
        "check_in_time",
        "updated_at",
    )
    list_filter = ("status", "appointment_date", "doctor")
    search_fields = (
        "patient__email",
        "patient__first_name",
        "patient__last_name",
        "doctor__email",
        "doctor__first_name",
        "doctor__last_name",
    )

admin.site.register(RescheduleHistory)
admin.site.register(AppointmentAuditLog)
admin.site.register(ConsultationRecord)
admin.site.register(PrescriptionItem)