from __future__ import annotations

from datetime import datetime, timedelta

from django.conf import settings
from django.contrib.auth import get_user_model
from django.db import IntegrityError, transaction
from django.shortcuts import get_object_or_404
from django.utils import timezone
from django.utils.translation import gettext_lazy as _
from rest_framework.exceptions import PermissionDenied, ValidationError

from appointments.models import (
	Appointment,
	AppointmentAuditLog,
	AppointmentStatus,
	AuditAction,
	ConsultationRecord,
	PrescriptionItem,
	RescheduleHistory,
)
from slots.models import Slot

User = get_user_model()


class BookingConflictError(Exception):
	pass


EXCLUDED_CONFLICT_STATUSES = [
	AppointmentStatus.CANCELLED,
	AppointmentStatus.NO_SHOW,
]

ALLOWED_RESCHEDULE_STATUSES = [
	AppointmentStatus.REQUESTED,
	AppointmentStatus.CONFIRMED,
]


def get_primary_role(user) -> str | None:
	if not user or not user.is_authenticated:
		return None

	group_names = set(user.groups.values_list("name", flat=True))
	for role in ["Admin", "Doctor", "Receptionist", "Patient"]:
		if role in group_names:
			return role
	return None


def ensure_object_access(*, user, appointment: Appointment) -> None:
	role = get_primary_role(user)
	if role is None:
		raise PermissionDenied("You do not have permission to access this appointment.")

	if role == "Patient" and appointment.patient_id != user.id:
		raise PermissionDenied("You do not have permission to access this appointment.")

	if role == "Doctor" and appointment.doctor_id != user.id:
		raise PermissionDenied("You do not have permission to access this appointment.")

	if role not in {"Admin", "Receptionist", "Doctor", "Patient"}:
		raise PermissionDenied("You do not have permission to access this appointment.")


def get_appointment_for_access_check(appointment_id: int) -> Appointment:
	return get_object_or_404(
		Appointment.objects.select_related("patient", "doctor", "slot").prefetch_related(
			"consultation_record__prescription_items"
		),
		id=appointment_id,
	)


def get_appointment_for_list_queryset():
	return Appointment.objects.select_related("patient", "doctor", "slot").prefetch_related(
		"consultation_record__prescription_items"
	)


def scope_queryset_for_user(queryset, user):
	role = get_primary_role(user)
	if role == "Patient":
		return queryset.filter(patient=user), role
	if role == "Doctor":
		return queryset.filter(doctor=user), role
	if role in {"Receptionist", "Admin"}:
		return queryset, role

	raise PermissionDenied("You do not have permission to access appointments.")


def _validate_slot_not_in_past(slot: Slot) -> None:
	slot_start = datetime.combine(slot.date, slot.start_time)
	if timezone.is_aware(timezone.now()):
		slot_start = timezone.make_aware(slot_start, timezone.get_current_timezone())

	if slot_start <= timezone.now():
		raise ValidationError({"new_slot_id": _("Cannot reschedule to a past date or time.")})


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
	exclude_appointment_id: int | None = None,
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
		.only("id", "appointment_time", "session_duration_minutes")
	)
	if exclude_appointment_id is not None:
		patient_same_day_appointments = patient_same_day_appointments.exclude(id=exclude_appointment_id)

	for existing_appointment in patient_same_day_appointments:
		existing_start = datetime.combine(appointment_date, existing_appointment.appointment_time)
		existing_end = existing_start + timedelta(minutes=existing_appointment.session_duration_minutes)

		if existing_start < requested_window_end and existing_end > requested_window_start:
			return True

	return False


def _doctor_has_time_conflict(
	*,
	doctor,
	appointment_date,
	appointment_time,
	duration_minutes: int,
	buffer_minutes: int,
	exclude_appointment_id: int | None = None,
) -> bool:
	requested_window_start, requested_window_end = _build_appointment_window(
		appointment_date=appointment_date,
		appointment_time=appointment_time,
		duration_minutes=duration_minutes,
		buffer_minutes=buffer_minutes,
	)

	doctor_same_day_appointments = (
		Appointment.objects.select_for_update(nowait=False)
		.filter(
			doctor=doctor,
			appointment_date=appointment_date,
		)
		.exclude(status__in=EXCLUDED_CONFLICT_STATUSES)
		.only("id", "appointment_time", "session_duration_minutes")
	)
	if exclude_appointment_id is not None:
		doctor_same_day_appointments = doctor_same_day_appointments.exclude(id=exclude_appointment_id)

	for existing_appointment in doctor_same_day_appointments:
		existing_start = datetime.combine(appointment_date, existing_appointment.appointment_time)
		existing_end = existing_start + timedelta(minutes=existing_appointment.session_duration_minutes)

		if existing_start < requested_window_end and existing_end > requested_window_start:
			return True

	return False
def _write_audit_log(
	*,
	appointment: Appointment,
	actor,
	action: str,
	from_status: str,
	to_status: str,
	notes: str = "",
) -> None:
	AppointmentAuditLog.objects.create(
		appointment=appointment,
		actor=actor,
		action=action,
		from_status=from_status,
		to_status=to_status,
		notes=notes,
	)


def _lock_slot(slot_id: int) -> Slot:
	slot = (
		Slot.objects.select_for_update(nowait=False)
		.select_related("doctor")
		.filter(id=slot_id)
		.first()
	)
	if slot is None:
		raise ValidationError({"new_slot_id": _("Invalid slot.")})
	return slot


def _lock_appointment(appointment_id: int) -> Appointment:
	appointment = (
		Appointment.objects.select_for_update(nowait=False)
		.filter(id=appointment_id)
		.first()
	)
	if appointment is None:
		raise ValidationError({"detail": _("Appointment not found.")})
	return appointment


def _set_slot_availability(slot: Slot | None, available: bool) -> None:
	if slot is None:
		return
	slot.is_available = available
	slot.save(update_fields=["is_available", "updated_at"])


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

		if _doctor_has_time_conflict(
			doctor=doctor,
			appointment_date=appointment_date,
			appointment_time=appointment_time,
		):
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

		_set_slot_availability(slot, False)

		_write_audit_log(
			appointment=appointment,
			actor=patient,
			action=AuditAction.BOOKED,
			from_status="",
			to_status=AppointmentStatus.REQUESTED,
			notes="Booked by patient.",
		)

		return appointment


def cancel_appointment(*, appointment_id: int, actor) -> Appointment:
	role = get_primary_role(actor)
	if role not in {"Patient", "Receptionist"}:
		raise PermissionDenied("You do not have permission to cancel appointments.")

	with transaction.atomic():
		appointment = _lock_appointment(appointment_id)

		if role == "Patient" and appointment.patient_id != actor.id:
			raise PermissionDenied("You can cancel only your own appointments.")

		if appointment.status == AppointmentStatus.CHECKED_IN:
			raise ValidationError({"detail": "Cannot cancel once checked in."})

		if appointment.status == AppointmentStatus.NO_SHOW:
			raise ValidationError({"detail": "Cannot transition appointment after NO_SHOW."})

		if appointment.status not in [AppointmentStatus.REQUESTED, AppointmentStatus.CONFIRMED]:
			raise ValidationError(
				{"detail": f"Cannot cancel appointment while status is {appointment.status}."}
			)

		old_status = appointment.status
		appointment.status = AppointmentStatus.CANCELLED
		appointment.save(update_fields=["status", "updated_at"])
		_set_slot_availability(appointment.slot, True)

		_write_audit_log(
			appointment=appointment,
			actor=actor,
			action=AuditAction.CANCELLED,
			from_status=old_status,
			to_status=AppointmentStatus.CANCELLED,
			notes="Cancelled appointment.",
		)

		return appointment


def confirm_appointment(*, appointment_id: int, actor) -> Appointment:
	if get_primary_role(actor) != "Doctor":
		raise PermissionDenied("Only doctors can confirm appointments.")

	with transaction.atomic():
		appointment = _lock_appointment(appointment_id)

		if appointment.doctor_id != actor.id:
			raise PermissionDenied("You can only confirm your own appointments.")

		if appointment.status == AppointmentStatus.CONFIRMED:
			raise ValidationError({"detail": "Appointment is already CONFIRMED."})

		if appointment.status != AppointmentStatus.REQUESTED:
			raise ValidationError({"detail": "Only REQUESTED appointments can be confirmed."})

		old_status = appointment.status
		appointment.status = AppointmentStatus.CONFIRMED
		appointment.save(update_fields=["status", "updated_at"])

		_write_audit_log(
			appointment=appointment,
			actor=actor,
			action=AuditAction.CONFIRMED,
			from_status=old_status,
			to_status=AppointmentStatus.CONFIRMED,
			notes="Doctor confirmed appointment.",
		)

		return appointment


def decline_appointment(*, appointment_id: int, actor, reason: str = "") -> Appointment:
	if get_primary_role(actor) != "Doctor":
		raise PermissionDenied("Only doctors can decline appointments.")

	with transaction.atomic():
		appointment = _lock_appointment(appointment_id)

		if appointment.doctor_id != actor.id:
			raise PermissionDenied("You can only decline your own appointments.")

		if appointment.status != AppointmentStatus.REQUESTED:
			raise ValidationError({"detail": "Only REQUESTED appointments can be declined."})

		old_status = appointment.status
		appointment.status = AppointmentStatus.CANCELLED
		appointment.save(update_fields=["status", "updated_at"])
		_set_slot_availability(appointment.slot, True)

		_write_audit_log(
			appointment=appointment,
			actor=actor,
			action=AuditAction.DECLINED,
			from_status=old_status,
			to_status=AppointmentStatus.CANCELLED,
			notes=reason.strip(),
		)

		return appointment


def check_in_appointment(*, appointment_id: int, actor, client_sent_check_in_time: bool = False) -> Appointment:
	if get_primary_role(actor) != "Receptionist":
		raise PermissionDenied("Only receptionists can check in patients.")

	if client_sent_check_in_time:
		raise ValidationError({"check_in_time": "check_in_time is set by the server."})

	with transaction.atomic():
		appointment = _lock_appointment(appointment_id)

		if appointment.status == AppointmentStatus.REQUESTED:
			raise ValidationError(
				{"detail": "Cannot check in a REQUESTED appointment. It must be CONFIRMED first."}
			)

		if appointment.status != AppointmentStatus.CONFIRMED:
			raise ValidationError({"detail": "Only CONFIRMED appointments can be checked in."})

		old_status = appointment.status
		appointment.status = AppointmentStatus.CHECKED_IN
		appointment.check_in_time = timezone.now()
		appointment.save(update_fields=["status", "check_in_time", "updated_at"])

		_write_audit_log(
			appointment=appointment,
			actor=actor,
			action=AuditAction.CHECKED_IN,
			from_status=old_status,
			to_status=AppointmentStatus.CHECKED_IN,
			notes="Receptionist checked in patient.",
		)

		return appointment


def mark_no_show(*, appointment_id: int, actor) -> Appointment:
	role = get_primary_role(actor)
	if role not in {"Doctor", "Receptionist"}:
		raise PermissionDenied("Only doctor or receptionist can mark no-show.")

	with transaction.atomic():
		appointment = _lock_appointment(appointment_id)

		if role == "Doctor" and appointment.doctor_id != actor.id:
			raise PermissionDenied("You can only mark no-show on your own appointments.")

		if appointment.status == AppointmentStatus.NO_SHOW:
			raise ValidationError({"detail": "Cannot transition appointment after NO_SHOW."})

		if appointment.status == AppointmentStatus.CONFIRMED:
			raise ValidationError({"detail": "Cannot mark no-show before check-in."})

		if appointment.status != AppointmentStatus.CHECKED_IN:
			raise ValidationError({"detail": "Only CHECKED_IN appointments can be marked as NO_SHOW."})

		old_status = appointment.status
		appointment.status = AppointmentStatus.NO_SHOW
		appointment.save(update_fields=["status", "updated_at"])
		_set_slot_availability(appointment.slot, True)

		_write_audit_log(
			appointment=appointment,
			actor=actor,
			action=AuditAction.NO_SHOW,
			from_status=old_status,
			to_status=AppointmentStatus.NO_SHOW,
			notes="Marked as no-show.",
		)

		return appointment


def reschedule_appointment(*, appointment_id: int, actor, new_slot_id: int, reason: str = "") -> Appointment:
	role = get_primary_role(actor)
	if role not in {"Patient", "Receptionist"}:
		raise PermissionDenied("Only patient or receptionist can reschedule appointments.")

	buffer_minutes = int(getattr(settings, "APPOINTMENT_BUFFER_MINUTES", 5))

	with transaction.atomic():
		appointment = _lock_appointment(appointment_id)
		if role == "Patient" and appointment.patient_id != actor.id:
			raise PermissionDenied("You can reschedule only your own appointments.")

		if appointment.status == AppointmentStatus.NO_SHOW:
			raise ValidationError({"detail": "Cannot transition appointment after NO_SHOW."})

		if appointment.status not in ALLOWED_RESCHEDULE_STATUSES:
			raise ValidationError(
				{"detail": f"Cannot reschedule appointment while status is {appointment.status}."}
			)

		old_slot = appointment.slot
		old_date = appointment.appointment_date
		old_time = appointment.appointment_time

		new_slot = _lock_slot(new_slot_id)
		if not new_slot.is_available:
			raise BookingConflictError("Selected slot is no longer available.")

		if old_slot and old_slot.id == new_slot.id:
			raise ValidationError({"new_slot_id": "New slot must be different from current slot."})

		_validate_slot_not_in_past(new_slot)

		if _doctor_has_time_conflict(
			doctor=new_slot.doctor,
			appointment_date=new_slot.date,
			appointment_time=new_slot.start_time,
			exclude_appointment_id=appointment.id,
		):
			raise BookingConflictError("Doctor is already booked for this date and time.")

		if _patient_has_overlap(
			patient_id=appointment.patient_id,
			appointment_date=new_slot.date,
			appointment_time=new_slot.start_time,
			duration_minutes=new_slot.duration_minutes,
			buffer_minutes=buffer_minutes,
			exclude_appointment_id=appointment.id,
		):
			raise BookingConflictError("Patient has an overlapping appointment.")

		old_status = appointment.status
		appointment.slot = new_slot
		appointment.doctor = new_slot.doctor
		appointment.appointment_date = new_slot.date
		appointment.appointment_time = new_slot.start_time
		appointment.session_duration_minutes = new_slot.duration_minutes

		if old_status == AppointmentStatus.CONFIRMED:
			appointment.status = AppointmentStatus.CONFIRMED

		appointment.save(
			update_fields=[
				"slot",
				"doctor",
				"appointment_date",
				"appointment_time",
				"session_duration_minutes",
				"status",
				"updated_at",
			]
		)

		_set_slot_availability(old_slot, True)
		_set_slot_availability(new_slot, False)

		RescheduleHistory.objects.create(
			appointment=appointment,
			old_date=old_date,
			old_time=old_time,
			new_date=new_slot.date,
			new_time=new_slot.start_time,
			changed_by=actor,
			reason=reason.strip(),
		)

		_write_audit_log(
			appointment=appointment,
			actor=actor,
			action=AuditAction.RESCHEDULED,
			from_status=old_status,
			to_status=appointment.status,
			notes=reason.strip(),
		)

		return appointment


def file_consultation(
	*,
	appointment_id: int,
	actor,
	diagnosis: str,
	notes: str = "",
	requested_tests: list[str] | None = None,
	prescription_items: list[dict] | None = None,
) -> Appointment:
	if get_primary_role(actor) != "Doctor":
		raise PermissionDenied("Only doctors can file consultations.")

	requested_tests = requested_tests or []
	prescription_items = prescription_items or []

	with transaction.atomic():
		appointment = _lock_appointment(appointment_id)

		if appointment.doctor_id != actor.id:
			raise PermissionDenied("You can only file consultations for your own appointments.")

		if appointment.status != AppointmentStatus.CHECKED_IN:
			raise ValidationError(
				{"detail": "Consultation can only be filed for CHECKED_IN appointments."}
			)

		already_exists = (
			ConsultationRecord.objects.select_for_update(nowait=False)
			.filter(appointment=appointment)
			.exists()
		)
		if already_exists:
			raise ValidationError({"detail": "Consultation already filed"})

		consultation = ConsultationRecord.objects.create(
			appointment=appointment,
			diagnosis=diagnosis,
			notes=notes,
			requested_tests="\n".join(test.strip() for test in requested_tests if test.strip()),
			created_by=actor,
		)

		if prescription_items:
			PrescriptionItem.objects.bulk_create(
				[
					PrescriptionItem(
						consultation_record=consultation,
						drug=item["drug"],
						dose=item["dose"],
						duration=item["duration"],
						instructions=item.get("instructions", ""),
					)
					for item in prescription_items
				]
			)

		old_status = appointment.status
		appointment.status = AppointmentStatus.COMPLETED
		appointment.save(update_fields=["status", "updated_at"])

		_write_audit_log(
			appointment=appointment,
			actor=actor,
			action=AuditAction.COMPLETED,
			from_status=old_status,
			to_status=AppointmentStatus.COMPLETED,
			notes="Consultation filed and appointment completed.",
		)

		return appointment
