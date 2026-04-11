from __future__ import annotations

import datetime as dt

from django.conf import settings
from django.db import models
from django.utils import timezone


class Appointment(models.Model):
    class Status(models.TextChoices):
        REQUESTED = "requested", "Requested"
        CONFIRMED = "confirmed", "Confirmed"
        CHECKED_IN = "checked_in", "Checked in"
        COMPLETED = "completed", "Completed"
        CANCELLED = "cancelled", "Cancelled"
        NO_SHOW = "no_show", "No show"

    patient = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="patient_appointments",
        limit_choices_to={"groups__name": "Patient"},
    )

    doctor = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="doctor_appointments",
        limit_choices_to={"groups__name": "Doctor"},
    )
    date = models.DateField(db_index=True)
    time = models.TimeField(db_index=True)
    session_duration = models.IntegerField(choices=[(15, "15"), (30, "30")])
    status = models.CharField(max_length=16, choices=Status, default=Status.REQUESTED)
    reason = models.TextField()
    check_in_time = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ("date", "time")
        unique_together = ("doctor", "date", "time")

    @property
    def starts_at(self) -> dt.datetime:
        return timezone.make_aware(
            dt.datetime.combine(self.date, self.time),
            timezone.get_current_timezone(),
        )

    @property
    def ends_at(self) -> dt.datetime:
        return self.starts_at + dt.timedelta(minutes=self.session_duration)

    def __str__(self) -> str:
        return f"Appointment {self.pk} - Dr.{self.doctor_id} / Pt.{self.patient_id} ({self.status})"
