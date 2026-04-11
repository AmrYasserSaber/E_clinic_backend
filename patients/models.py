from __future__ import annotations

from django.conf import settings
from django.core.validators import RegexValidator
from django.db import models
from django.utils.translation import gettext_lazy as _

from users.models import EGYPTIAN_PHONE_REGEX


def _validate_optional_egyptian_phone(value: str | None) -> None:
    if value in (None, ""):
        return
    RegexValidator(regex=EGYPTIAN_PHONE_REGEX, message=_("Invalid phone number."))(value)


class PatientProfile(models.Model):
    class BloodType(models.TextChoices):
        A_POS = "A+", "A+"
        A_NEG = "A-", "A-"
        B_POS = "B+", "B+"
        B_NEG = "B-", "B-"
        AB_POS = "AB+", "AB+"
        AB_NEG = "AB-", "AB-"
        O_POS = "O+", "O+"
        O_NEG = "O-", "O-"
        UNKNOWN = "unknown", _("Unknown")

    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="patient_profile",
    )
    blood_type = models.CharField(
        max_length=8,
        choices=BloodType,
        blank=True,
    )
    emergency_contact_name = models.CharField(max_length=150, blank=True)
    emergency_contact_phone = models.CharField(
        max_length=11,
        blank=True,
        validators=[_validate_optional_egyptian_phone],
    )
    address = models.TextField(blank=True)
    notes = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = _("patient profile")
        verbose_name_plural = _("patient profiles")
        ordering = ("-updated_at",)

    def __str__(self) -> str:
        return f"Profile: {self.user.get_full_name()}"
