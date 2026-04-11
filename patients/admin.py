from __future__ import annotations

from django.contrib import admin

from patients.models import PatientProfile


@admin.register(PatientProfile)
class PatientProfileAdmin(admin.ModelAdmin):
    list_display = ("user", "emergency_contact_name", "updated_at")
    search_fields = (
        "user__email",
        "user__first_name",
        "user__last_name",
        "emergency_contact_name",
    )
    raw_id_fields = ("user",)
    readonly_fields = ("created_at", "updated_at")
