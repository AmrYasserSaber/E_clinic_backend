from __future__ import annotations

from django.conf import settings
from django.core.exceptions import ValidationError
from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import models


class DoctorSchedule(models.Model):
    doctor = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="doctor_schedules",
        limit_choices_to={"groups__name": "Doctor"},
    )
    day_of_week = models.IntegerField(
        validators=[MinValueValidator(0), MaxValueValidator(6)],
        help_text="0=Monday, 6=Sunday",
    )
    start_time = models.TimeField()
    end_time = models.TimeField()
    session_duration_minutes = models.IntegerField(
        validators=[MinValueValidator(1)],
        help_text="Duration of each session in minutes",
    )
    buffer_minutes = models.IntegerField(
        default=5,
        validators=[MinValueValidator(0)],
        help_text="Buffer time between sessions in minutes",
    )

    class Meta:
        unique_together = ("doctor", "day_of_week")
        ordering = ["doctor", "day_of_week", "start_time"]

    def clean(self) -> None:
        super().clean()
        if self.end_time and self.start_time and self.end_time <= self.start_time:
            raise ValidationError({"end_time": "end_time must be later than start_time."})

    def __str__(self) -> str:
        return (
            f"Dr. {self.doctor} - day {self.day_of_week} "
            f"({self.start_time} to {self.end_time})"
        )


class ScheduleException(models.Model):
    EXCEPTION_DAY_OFF = "day_off"
    EXCEPTION_ONE_OFF = "one_off"

    EXCEPTION_TYPE_CHOICES = [
        (EXCEPTION_DAY_OFF, "Day Off"),
        (EXCEPTION_ONE_OFF, "One Off"),
    ]

    doctor = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="schedule_exceptions",
        limit_choices_to={"groups__name": "Doctor"},
    )
    start_date = models.DateField()
    end_date = models.DateField(null=True, blank=True)
    exception_type = models.CharField(max_length=20, choices=EXCEPTION_TYPE_CHOICES)
    custom_start_time = models.TimeField(null=True, blank=True)
    custom_end_time = models.TimeField(null=True, blank=True)
    reason = models.TextField(blank=True)

    class Meta:
        ordering = ["doctor", "start_date"]

    def clean(self) -> None:
        super().clean()

        if self.end_date and self.end_date < self.start_date:
            raise ValidationError({"end_date": "end_date cannot be earlier than start_date."})

        if self.exception_type == self.EXCEPTION_DAY_OFF:
            if self.custom_start_time or self.custom_end_time:
                raise ValidationError(
                    "For day_off exception, custom_start_time and custom_end_time must be empty."
                )

        if self.exception_type == self.EXCEPTION_ONE_OFF:
            if not self.custom_start_time or not self.custom_end_time:
                raise ValidationError(
                    "For one_off exception, custom_start_time and custom_end_time are required."
                )
            if self.custom_end_time <= self.custom_start_time:
                raise ValidationError({"custom_end_time": "custom_end_time must be later than custom_start_time."})

    def __str__(self) -> str:
        effective_end = self.end_date or self.start_date
        return f"{self.doctor} - {self.exception_type} ({self.start_date} to {effective_end})"
