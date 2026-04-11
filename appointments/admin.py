from django.contrib import admin

from appointments.models import Appointment


@admin.register(Appointment)
class AppointmentAdmin(admin.ModelAdmin):
    list_display = ("id", "doctor", "starts_at", "ends_at", "status")
    list_filter = ("status",)
