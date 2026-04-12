from django.conf import settings
from django.db import models

# STUB — to be replaced/extended by Dev2. Do not add business logic here.


class Slot(models.Model):
    doctor = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="slots",
    )
    date = models.DateField()
    start_time = models.TimeField()
    end_time = models.TimeField()
    is_available = models.BooleanField(default=True)
    duration_minutes = models.IntegerField(default=30)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        indexes = [
            models.Index(fields=["doctor", "date", "start_time"]),
            models.Index(fields=["date", "is_available"]),
        ]

    def __str__(self) -> str:
        return f"Slot #{self.pk} ({self.date} {self.start_time})"
