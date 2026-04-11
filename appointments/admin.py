from django.contrib import admin

from appointments.models import (
    Appointment,
    AppointmentAuditLog,
    ConsultationRecord,
    PrescriptionItem,
    RescheduleHistory,
)

admin.site.register(Appointment)
admin.site.register(RescheduleHistory)
admin.site.register(AppointmentAuditLog)
admin.site.register(ConsultationRecord)
admin.site.register(PrescriptionItem)
