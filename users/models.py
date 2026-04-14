from __future__ import annotations

from datetime import date

from django.contrib.auth.models import AbstractUser
from django.core.exceptions import ValidationError
from django.core.validators import RegexValidator
from django.db import models
from django.utils.translation import gettext_lazy as _

from users.managers import UserManager

EGYPTIAN_PHONE_REGEX: str = r"^01[0125]{1}[0-9]{8}$"


def validate_phone_number(value: str | None) -> None:
    if value in (None, ""):
        return
    validator = RegexValidator(regex=EGYPTIAN_PHONE_REGEX, message=_("Invalid phone number."))
    validator(value)


def validate_date_of_birth(value: date) -> None:
    if value is None:
        return
    if value >= date.today():
        raise ValidationError("dateOfBirth must be in the past.")


class User(AbstractUser):
    username = None
    email = models.EmailField(_("email address"), unique=True)
    first_name = models.CharField(max_length=150, blank=False)
    last_name = models.CharField(max_length=150, blank=False)
    phone_number = models.CharField(
        max_length=11,
        blank=True,
        null=True,
        validators=[validate_phone_number],
    )
    specialty = models.CharField(max_length=255, blank=True)
    date_of_birth = models.DateField(blank=True, null=True, validators=[validate_date_of_birth])
    is_approved = models.BooleanField(default=False)
    google_sub = models.CharField(max_length=255, blank=True, null=True, unique=True)
    google_email = models.EmailField(blank=True, null=True)
    google_linked_at = models.DateTimeField(blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    USERNAME_FIELD = "email"
    REQUIRED_FIELDS = ["first_name", "last_name"]

    objects = UserManager()

    class Meta:
        permissions = [
            ("manage_appointments", "Can manage appointments"),
            ("view_users", "Can view users"),
            ("create_users", "Can create users"),
        ]

