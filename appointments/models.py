from __future__ import annotations

from django.conf import settings
from django.db import models


class AppointmentStatus(models.TextChoices):
    REQUESTED = "REQUESTED", "Requested"
    CONFIRMED = "CONFIRMED", "Confirmed"
    CHECKED_IN = "CHECKED_IN", "Checked In"
    COMPLETED = "COMPLETED", "Completed"
    CANCELLED = "CANCELLED", "Cancelled"
    NO_SHOW = "NO_SHOW", "No Show"


class AuditAction(models.TextChoices):
    BOOKED = "BOOKED", "Booked"
    CONFIRMED = "CONFIRMED", "Confirmed"
    DECLINED = "DECLINED", "Declined"
    CANCELLED = "CANCELLED", "Cancelled"
    CHECKED_IN = "CHECKED_IN", "Checked In"
    NO_SHOW = "NO_SHOW", "No Show"
    RESCHEDULED = "RESCHEDULED", "Rescheduled"
    COMPLETED = "COMPLETED", "Completed"


class Appointment(models.Model):
    patient = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="patient_appointments",
    )
    doctor = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="doctor_appointments",
    )
    slot = models.ForeignKey(
        "slots.Slot",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="appointments",
    )
    appointment_date = models.DateField()
    appointment_time = models.TimeField()
    reason = models.TextField(blank=True)
    session_duration_minutes = models.PositiveSmallIntegerField(default=30)
    status = models.CharField(
        max_length=20,
        choices=AppointmentStatus.choices,
        default=AppointmentStatus.REQUESTED,
    )
    check_in_time = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["doctor", "appointment_date", "appointment_time"],
                name="uniq_appointment_doctor_date_time",
            )
        ]
        indexes = [
            models.Index(fields=["patient", "appointment_date"]),
            models.Index(fields=["doctor", "appointment_date"]),
            models.Index(fields=["status"]),
            models.Index(fields=["appointment_date", "appointment_time"]),
        ]
        ordering = ["-appointment_date", "-appointment_time", "-id"]

    def __str__(self) -> str:
        return f"Appointment #{self.pk} ({self.status})"


class RescheduleHistory(models.Model):
    appointment = models.ForeignKey(
        Appointment,
        on_delete=models.CASCADE,
        related_name="reschedule_history",
    )
    old_date = models.DateField()
    old_time = models.TimeField()
    new_date = models.DateField()
    new_time = models.TimeField()
    changed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="appointment_reschedules",
    )
    reason = models.TextField(blank=True)
    changed_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-changed_at", "-id"]


class AppointmentAuditLog(models.Model):
    appointment = models.ForeignKey(
        Appointment,
        on_delete=models.CASCADE,
        related_name="audit_logs",
    )
    actor = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="appointment_audit_logs",
    )
    action = models.CharField(max_length=20, choices=AuditAction.choices)
    from_status = models.CharField(max_length=20, choices=AppointmentStatus.choices, blank=True)
    to_status = models.CharField(max_length=20, choices=AppointmentStatus.choices, blank=True)
    notes = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at", "-id"]


class ConsultationRecord(models.Model):
    appointment = models.OneToOneField(
        Appointment,
        on_delete=models.CASCADE,
        related_name="consultation_record",
    )
    diagnosis = models.TextField()
    notes = models.TextField(blank=True)
    requested_tests = models.TextField(blank=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="consultation_records",
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)


class PrescriptionItem(models.Model):
    consultation_record = models.ForeignKey(
        ConsultationRecord,
        on_delete=models.CASCADE,
        related_name="prescription_items",
    )
    drug = models.CharField(max_length=255)
    dose = models.CharField(max_length=255)
    duration = models.CharField(max_length=255)
    instructions = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
