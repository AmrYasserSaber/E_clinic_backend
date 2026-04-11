from __future__ import annotations

from datetime import datetime, timedelta

from django.conf import settings
from django.contrib.auth import get_user_model
from django.db import IntegrityError, transaction
from django.utils.translation import gettext_lazy as _
from rest_framework.exceptions import ValidationError

from appointments.models import Appointment, AppointmentAuditLog, AppointmentStatus, AuditAction
from slots.models import Slot

User = get_user_model()


class BookingConflictError(Exception):
	pass


EXCLUDED_CONFLICT_STATUSES = [
	AppointmentStatus.CANCELLED,
	AppointmentStatus.NO_SHOW,
]


def _build_appointment_window(
	appointment_date,
	appointment_time,
	duration_minutes: int,
	buffer_minutes: int,
):
	appointment_start = datetime.combine(appointment_date, appointment_time)
	appointment_end = appointment_start + timedelta(minutes=duration_minutes)
	return (
		appointment_start - timedelta(minutes=buffer_minutes),
		appointment_end + timedelta(minutes=buffer_minutes),
	)


def _patient_has_overlap(
	*,
	patient_id: int,
	appointment_date,
	appointment_time,
	duration_minutes: int,
	buffer_minutes: int,
) -> bool:
	requested_window_start, requested_window_end = _build_appointment_window(
		appointment_date=appointment_date,
		appointment_time=appointment_time,
		duration_minutes=duration_minutes,
		buffer_minutes=buffer_minutes,
	)

	patient_same_day_appointments = (
		Appointment.objects.select_for_update(nowait=False)
		.filter(patient_id=patient_id, appointment_date=appointment_date)
		.exclude(status__in=EXCLUDED_CONFLICT_STATUSES)
		.only("appointment_time", "session_duration_minutes")
	)

	for existing_appointment in patient_same_day_appointments:
		existing_start = datetime.combine(appointment_date, existing_appointment.appointment_time)
		existing_end = existing_start + timedelta(minutes=existing_appointment.session_duration_minutes)

		if existing_start < requested_window_end and existing_end > requested_window_start:
			return True

	return False


def book_appointment(
	*,
	patient,
	slot_id: int | None = None,
	doctor_id: int | None = None,
	appointment_date=None,
	appointment_time=None,
	session_duration_minutes: int = 30,
) -> Appointment:
	buffer_minutes = int(getattr(settings, "APPOINTMENT_BUFFER_MINUTES", 5))

	with transaction.atomic():
		slot = None
		doctor = None

		if slot_id is not None:
			slot = (
				Slot.objects.select_for_update(nowait=False)
				.select_related("doctor")
				.filter(id=slot_id)
				.first()
			)
			if slot is None:
				raise ValidationError({"slot_id": _("Invalid slot.")})
			if not slot.is_available:
				raise BookingConflictError("Selected slot is no longer available.")

			doctor = slot.doctor
			appointment_date = slot.date
			appointment_time = slot.start_time
			session_duration_minutes = slot.duration_minutes
		else:
			if not doctor_id or not appointment_date or not appointment_time:
				raise ValidationError(
					{
						"detail": _(
							"doctor_id, appointment_date, and appointment_time are required when slot_id is not provided."
						)
					}
				)

			doctor = (
				User.objects.select_for_update(nowait=False)
				.filter(id=doctor_id, groups__name="Doctor")
				.first()
			)
			if doctor is None:
				raise ValidationError({"doctor_id": _("Invalid doctor.")})

		doctor_conflict_exists = (
			Appointment.objects.select_for_update(nowait=False)
			.filter(
				doctor=doctor,
				appointment_date=appointment_date,
				appointment_time=appointment_time,
			)
			.exclude(status__in=EXCLUDED_CONFLICT_STATUSES)
			.exists()
		)
		if doctor_conflict_exists:
			raise BookingConflictError("Doctor is already booked for this date and time.")

		if _patient_has_overlap(
			patient_id=patient.id,
			appointment_date=appointment_date,
			appointment_time=appointment_time,
			duration_minutes=session_duration_minutes,
			buffer_minutes=buffer_minutes,
		):
			raise BookingConflictError("Patient has an overlapping appointment.")

		try:
			appointment = Appointment.objects.create(
				patient=patient,
				doctor=doctor,
				slot=slot,
				appointment_date=appointment_date,
				appointment_time=appointment_time,
				session_duration_minutes=session_duration_minutes,
				status=AppointmentStatus.REQUESTED,
			)
		except IntegrityError as exc:
			raise BookingConflictError("Appointment slot is no longer available.") from exc

		if slot is not None:
			slot.is_available = False
			slot.save(update_fields=["is_available", "updated_at"])

		AppointmentAuditLog.objects.create(
			appointment=appointment,
			actor=patient,
			action=AuditAction.BOOKED,
			from_status="",
			to_status=AppointmentStatus.REQUESTED,
			notes="Booked by patient.",
		)

		return appointment
