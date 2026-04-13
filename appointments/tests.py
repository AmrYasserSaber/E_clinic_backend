from __future__ import annotations

from datetime import date, datetime, time, timedelta

from django.contrib.auth.models import Group
from django.utils import timezone
from rest_framework import status
from rest_framework.test import APIClient, APITestCase

from appointments.models import (
    Appointment,
    AppointmentStatus,
    ConsultationRecord,
    RescheduleHistory,
)
from slots.models import Slot
from users.models import User


class AppointmentApiTests(APITestCase):
    def setUp(self):
        self.patient_group, _ = Group.objects.get_or_create(name="Patient")
        self.doctor_group, _ = Group.objects.get_or_create(name="Doctor")
        self.receptionist_group, _ = Group.objects.get_or_create(name="Receptionist")
        self.admin_group, _ = Group.objects.get_or_create(name="Admin")

        self.patient = self._create_user("patient@example.com", "Patient", "One")
        self.patient.groups.add(self.patient_group)

        self.doctor = self._create_user(
            "doctor@example.com",
            "Doctor",
            "One",
            is_approved=True,
        )
        self.doctor.groups.add(self.doctor_group)

        self.receptionist = self._create_user(
            "receptionist@example.com",
            "Receptionist",
            "One",
            is_approved=True,
        )
        self.receptionist.groups.add(self.receptionist_group)

        self.admin = self._create_user(
            "admin@example.com",
            "Admin",
            "One",
            is_approved=True,
            is_staff=True,
        )
        self.admin.groups.add(self.admin_group)

        self.tomorrow = timezone.localdate() + timedelta(days=1)
        self.default_slot = self._create_slot(
            doctor=self.doctor,
            slot_date=self.tomorrow,
            start=time(10, 0),
            end=time(10, 30),
            is_available=True,
            duration_minutes=30,
        )

        self.patient_client = self._client_for(self.patient)
        self.doctor_client = self._client_for(self.doctor)
        self.receptionist_client = self._client_for(self.receptionist)
        self.admin_client = self._client_for(self.admin)

    def _create_user(
        self,
        email: str,
        first_name: str,
        last_name: str,
        *,
        is_approved: bool = True,
        is_staff: bool = False,
    ) -> User:
        return User.objects.create_user(
            email=email,
            password="StrongPass123!",
            first_name=first_name,
            last_name=last_name,
            phone_number="01012345678",
            date_of_birth=date(1995, 1, 1),
            is_approved=is_approved,
            is_staff=is_staff,
        )

    def _client_for(self, user: User) -> APIClient:
        client = APIClient()
        client.force_authenticate(user=user)
        return client

    def _create_slot(
        self,
        *,
        doctor: User,
        slot_date,
        start: time,
        end: time,
        is_available: bool = True,
        duration_minutes: int = 30,
    ) -> Slot:
        return Slot.objects.create(
            doctor=doctor,
            date=slot_date,
            start_time=start,
            end_time=end,
            is_available=is_available,
            duration_minutes=duration_minutes,
        )

    def _create_appointment(
        self,
        *,
        patient: User,
        doctor: User,
        appointment_date,
        appointment_time: time,
        status_value: str,
        slot: Slot | None = None,
        check_in_time=None,
        duration_minutes: int = 30,
    ) -> Appointment:
        return Appointment.objects.create(
            patient=patient,
            doctor=doctor,
            slot=slot,
            appointment_date=appointment_date,
            appointment_time=appointment_time,
            session_duration_minutes=duration_minutes,
            status=status_value,
            check_in_time=check_in_time,
        )

    # BOOKING
    def test_booking_valid_returns_201_and_requested(self):
        response = self.patient_client.post(
            "/api/appointments/",
            {"slot_id": self.default_slot.id},
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(response.data["status"], AppointmentStatus.REQUESTED)

    def test_booking_same_slot_twice_returns_409_on_second(self):
        other_patient = self._create_user("patient2@example.com", "Patient", "Two")
        other_patient.groups.add(self.patient_group)
        other_patient_client = self._client_for(other_patient)

        first_response = self.patient_client.post(
            "/api/appointments/",
            {"slot_id": self.default_slot.id},
            format="json",
        )
        second_response = other_patient_client.post(
            "/api/appointments/",
            {"slot_id": self.default_slot.id},
            format="json",
        )

        self.assertEqual(first_response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(second_response.status_code, status.HTTP_409_CONFLICT)

    def test_booking_doctor_double_booking_same_datetime_returns_409(self):
        self._create_appointment(
            patient=self.patient,
            doctor=self.doctor,
            appointment_date=self.tomorrow,
            appointment_time=time(11, 0),
            status_value=AppointmentStatus.REQUESTED,
        )

        response = self.patient_client.post(
            "/api/appointments/",
            {
                "doctor_id": self.doctor.id,
                "appointment_date": self.tomorrow.isoformat(),
                "appointment_time": "11:00:00",
            },
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_409_CONFLICT)

    def test_booking_patient_overlap_same_day_returns_409(self):
        first_slot = self._create_slot(
            doctor=self.doctor,
            slot_date=self.tomorrow,
            start=time(10, 0),
            end=time(10, 30),
            is_available=True,
            duration_minutes=30,
        )
        second_slot = self._create_slot(
            doctor=self.doctor,
            slot_date=self.tomorrow,
            start=time(10, 20),
            end=time(10, 50),
            is_available=True,
            duration_minutes=30,
        )

        first_response = self.patient_client.post(
            "/api/appointments/",
            {"slot_id": first_slot.id},
            format="json",
        )
        second_response = self.patient_client.post(
            "/api/appointments/",
            {"slot_id": second_slot.id},
            format="json",
        )

        self.assertEqual(first_response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(second_response.status_code, status.HTTP_409_CONFLICT)

    def test_booking_doctor_token_attempt_returns_403(self):
        response = self.doctor_client.post(
            "/api/appointments/",
            {"slot_id": self.default_slot.id},
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    # LISTING
    def test_listing_patient_returns_only_own_appointments(self):
        other_patient = self._create_user("patient3@example.com", "Patient", "Three")
        other_patient.groups.add(self.patient_group)

        own_appointment = self._create_appointment(
            patient=self.patient,
            doctor=self.doctor,
            appointment_date=self.tomorrow,
            appointment_time=time(9, 0),
            status_value=AppointmentStatus.REQUESTED,
        )
        self._create_appointment(
            patient=other_patient,
            doctor=self.doctor,
            appointment_date=self.tomorrow,
            appointment_time=time(9, 30),
            status_value=AppointmentStatus.REQUESTED,
        )

        response = self.patient_client.get("/api/appointments/")

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data), 1)
        self.assertEqual(response.data[0]["id"], own_appointment.id)

    def test_listing_patient_with_patient_id_param_returns_403(self):
        other_patient = self._create_user("patient4@example.com", "Patient", "Four")
        other_patient.groups.add(self.patient_group)

        response = self.patient_client.get(f"/api/appointments/?patient_id={other_patient.id}")
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_listing_status_filter_returns_only_confirmed(self):
        self._create_appointment(
            patient=self.patient,
            doctor=self.doctor,
            appointment_date=self.tomorrow,
            appointment_time=time(8, 0),
            status_value=AppointmentStatus.CONFIRMED,
        )
        self._create_appointment(
            patient=self.patient,
            doctor=self.doctor,
            appointment_date=self.tomorrow,
            appointment_time=time(8, 30),
            status_value=AppointmentStatus.REQUESTED,
        )

        response = self.patient_client.get("/api/appointments/?status=CONFIRMED")

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data), 1)
        self.assertEqual(response.data[0]["status"], AppointmentStatus.CONFIRMED)

    def test_listing_date_range_filters_are_inclusive(self):
        date_from = self.tomorrow
        date_mid = self.tomorrow + timedelta(days=1)
        date_to = self.tomorrow + timedelta(days=2)

        first = self._create_appointment(
            patient=self.patient,
            doctor=self.doctor,
            appointment_date=date_from,
            appointment_time=time(8, 0),
            status_value=AppointmentStatus.REQUESTED,
        )
        middle = self._create_appointment(
            patient=self.patient,
            doctor=self.doctor,
            appointment_date=date_mid,
            appointment_time=time(8, 30),
            status_value=AppointmentStatus.REQUESTED,
        )
        last = self._create_appointment(
            patient=self.patient,
            doctor=self.doctor,
            appointment_date=date_to,
            appointment_time=time(9, 0),
            status_value=AppointmentStatus.REQUESTED,
        )
        self._create_appointment(
            patient=self.patient,
            doctor=self.doctor,
            appointment_date=date_to + timedelta(days=1),
            appointment_time=time(9, 30),
            status_value=AppointmentStatus.REQUESTED,
        )

        response = self.patient_client.get(
            f"/api/appointments/?date_from={date_from.isoformat()}&date_to={date_to.isoformat()}"
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        ids = {item["id"] for item in response.data}
        self.assertSetEqual(ids, {first.id, middle.id, last.id})

    # CANCEL
    def test_cancel_requested_sets_cancelled_and_frees_slot(self):
        slot = self._create_slot(
            doctor=self.doctor,
            slot_date=self.tomorrow,
            start=time(11, 0),
            end=time(11, 30),
            is_available=False,
        )
        appointment = self._create_appointment(
            patient=self.patient,
            doctor=self.doctor,
            appointment_date=self.tomorrow,
            appointment_time=time(11, 0),
            status_value=AppointmentStatus.REQUESTED,
            slot=slot,
        )

        response = self.patient_client.patch(f"/api/appointments/{appointment.id}/cancel/", format="json")

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        appointment.refresh_from_db()
        slot.refresh_from_db()
        self.assertEqual(appointment.status, AppointmentStatus.CANCELLED)
        self.assertTrue(slot.is_available)

    def test_cancel_confirmed_sets_cancelled(self):
        appointment = self._create_appointment(
            patient=self.patient,
            doctor=self.doctor,
            appointment_date=self.tomorrow,
            appointment_time=time(11, 30),
            status_value=AppointmentStatus.CONFIRMED,
        )

        response = self.patient_client.patch(f"/api/appointments/{appointment.id}/cancel/", format="json")

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        appointment.refresh_from_db()
        self.assertEqual(appointment.status, AppointmentStatus.CANCELLED)

    def test_cancel_checked_in_returns_400(self):
        appointment = self._create_appointment(
            patient=self.patient,
            doctor=self.doctor,
            appointment_date=self.tomorrow,
            appointment_time=time(12, 0),
            status_value=AppointmentStatus.CHECKED_IN,
            check_in_time=timezone.now(),
        )

        response = self.patient_client.patch(f"/api/appointments/{appointment.id}/cancel/", format="json")

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_cancel_other_patients_appointment_returns_403(self):
        other_patient = self._create_user("patient5@example.com", "Patient", "Five")
        other_patient.groups.add(self.patient_group)

        appointment = self._create_appointment(
            patient=other_patient,
            doctor=self.doctor,
            appointment_date=self.tomorrow,
            appointment_time=time(12, 30),
            status_value=AppointmentStatus.REQUESTED,
        )

        response = self.patient_client.patch(f"/api/appointments/{appointment.id}/cancel/", format="json")
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    # CONFIRM
    def test_confirm_requested_by_own_doctor_sets_confirmed(self):
        appointment = self._create_appointment(
            patient=self.patient,
            doctor=self.doctor,
            appointment_date=self.tomorrow,
            appointment_time=time(13, 0),
            status_value=AppointmentStatus.REQUESTED,
        )

        response = self.doctor_client.patch(f"/api/appointments/{appointment.id}/confirm/", format="json")

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        appointment.refresh_from_db()
        self.assertEqual(appointment.status, AppointmentStatus.CONFIRMED)

    def test_confirm_already_confirmed_returns_400(self):
        appointment = self._create_appointment(
            patient=self.patient,
            doctor=self.doctor,
            appointment_date=self.tomorrow,
            appointment_time=time(13, 30),
            status_value=AppointmentStatus.CONFIRMED,
        )

        response = self.doctor_client.patch(f"/api/appointments/{appointment.id}/confirm/", format="json")
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_confirm_another_doctors_appointment_returns_403(self):
        other_doctor = self._create_user(
            "doctor2@example.com",
            "Doctor",
            "Two",
            is_approved=True,
        )
        other_doctor.groups.add(self.doctor_group)

        appointment = self._create_appointment(
            patient=self.patient,
            doctor=other_doctor,
            appointment_date=self.tomorrow,
            appointment_time=time(14, 0),
            status_value=AppointmentStatus.REQUESTED,
        )

        response = self.doctor_client.patch(f"/api/appointments/{appointment.id}/confirm/", format="json")
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    # RESCHEDULE
    def test_reschedule_valid_creates_history_and_swaps_slot_availability(self):
        old_slot = self._create_slot(
            doctor=self.doctor,
            slot_date=self.tomorrow,
            start=time(14, 30),
            end=time(15, 0),
            is_available=False,
        )
        new_slot = self._create_slot(
            doctor=self.doctor,
            slot_date=self.tomorrow + timedelta(days=1),
            start=time(9, 0),
            end=time(9, 30),
            is_available=True,
        )
        appointment = self._create_appointment(
            patient=self.patient,
            doctor=self.doctor,
            appointment_date=old_slot.date,
            appointment_time=old_slot.start_time,
            status_value=AppointmentStatus.CONFIRMED,
            slot=old_slot,
        )

        response = self.patient_client.patch(
            f"/api/appointments/{appointment.id}/reschedule/",
            {"new_slot_id": new_slot.id, "reason": "Need different time"},
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        appointment.refresh_from_db()
        old_slot.refresh_from_db()
        new_slot.refresh_from_db()

        self.assertEqual(appointment.slot_id, new_slot.id)
        self.assertEqual(appointment.status, AppointmentStatus.CONFIRMED)
        self.assertTrue(old_slot.is_available)
        self.assertFalse(new_slot.is_available)
        self.assertEqual(RescheduleHistory.objects.filter(appointment=appointment).count(), 1)

    def test_reschedule_to_past_date_returns_400(self):
        old_slot = self._create_slot(
            doctor=self.doctor,
            slot_date=self.tomorrow,
            start=time(15, 0),
            end=time(15, 30),
            is_available=False,
        )
        past_slot = self._create_slot(
            doctor=self.doctor,
            slot_date=timezone.localdate() - timedelta(days=1),
            start=time(9, 0),
            end=time(9, 30),
            is_available=True,
        )
        appointment = self._create_appointment(
            patient=self.patient,
            doctor=self.doctor,
            appointment_date=old_slot.date,
            appointment_time=old_slot.start_time,
            status_value=AppointmentStatus.REQUESTED,
            slot=old_slot,
        )

        response = self.patient_client.patch(
            f"/api/appointments/{appointment.id}/reschedule/",
            {"new_slot_id": past_slot.id, "reason": "Past test"},
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_reschedule_by_doctor_date_time_updates_appointment(self):
        appointment = self._create_appointment(
            patient=self.patient,
            doctor=self.doctor,
            appointment_date=self.tomorrow,
            appointment_time=time(10, 0),
            status_value=AppointmentStatus.REQUESTED,
            slot=None,
        )

        response = self.patient_client.patch(
            f"/api/appointments/{appointment.id}/reschedule/",
            {
                "doctor_id": self.doctor.id,
                "date": self.tomorrow.isoformat(),
                "time": "09:00:00",
                "reason": "Earlier works better",
            },
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        appointment.refresh_from_db()
        self.assertEqual(appointment.appointment_time.replace(second=0, microsecond=0), time(9, 0))
        self.assertIsNotNone(appointment.slot_id)
        self.assertEqual(RescheduleHistory.objects.filter(appointment=appointment).count(), 1)

    def test_reschedule_same_calendar_time_returns_400(self):
        appointment = self._create_appointment(
            patient=self.patient,
            doctor=self.doctor,
            appointment_date=self.tomorrow,
            appointment_time=time(10, 0),
            status_value=AppointmentStatus.REQUESTED,
            slot=None,
        )

        response = self.patient_client.patch(
            f"/api/appointments/{appointment.id}/reschedule/",
            {
                "doctor_id": self.doctor.id,
                "date": self.tomorrow.isoformat(),
                "time": "10:00:00",
            },
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_reschedule_invalid_time_returns_400(self):
        appointment = self._create_appointment(
            patient=self.patient,
            doctor=self.doctor,
            appointment_date=self.tomorrow,
            appointment_time=time(10, 0),
            status_value=AppointmentStatus.REQUESTED,
            slot=None,
        )

        response = self.patient_client.patch(
            f"/api/appointments/{appointment.id}/reschedule/",
            {
                "doctor_id": self.doctor.id,
                "date": self.tomorrow.isoformat(),
                "time": "09:07:00",
            },
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    # CHECK-IN
    def test_check_in_confirmed_by_receptionist_sets_checked_in_and_server_time(self):
        appointment = self._create_appointment(
            patient=self.patient,
            doctor=self.doctor,
            appointment_date=self.tomorrow,
            appointment_time=time(15, 30),
            status_value=AppointmentStatus.CONFIRMED,
        )

        response = self.receptionist_client.patch(
            f"/api/appointments/{appointment.id}/check-in/",
            {},
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        appointment.refresh_from_db()
        self.assertEqual(appointment.status, AppointmentStatus.CHECKED_IN)
        self.assertIsNotNone(appointment.check_in_time)

    def test_check_in_requested_returns_400(self):
        appointment = self._create_appointment(
            patient=self.patient,
            doctor=self.doctor,
            appointment_date=self.tomorrow,
            appointment_time=time(16, 0),
            status_value=AppointmentStatus.REQUESTED,
        )

        response = self.receptionist_client.patch(
            f"/api/appointments/{appointment.id}/check-in/",
            {},
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_check_in_patient_token_returns_403(self):
        appointment = self._create_appointment(
            patient=self.patient,
            doctor=self.doctor,
            appointment_date=self.tomorrow,
            appointment_time=time(16, 30),
            status_value=AppointmentStatus.CONFIRMED,
        )

        response = self.patient_client.patch(
            f"/api/appointments/{appointment.id}/check-in/",
            {},
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    # NO-SHOW
    def test_no_show_doctor_marks_checked_in_to_no_show(self):
        appointment = self._create_appointment(
            patient=self.patient,
            doctor=self.doctor,
            appointment_date=self.tomorrow,
            appointment_time=time(17, 0),
            status_value=AppointmentStatus.CHECKED_IN,
            check_in_time=timezone.now(),
        )

        response = self.doctor_client.patch(f"/api/appointments/{appointment.id}/no-show/", format="json")

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        appointment.refresh_from_db()
        self.assertEqual(appointment.status, AppointmentStatus.NO_SHOW)

    def test_no_show_on_confirmed_returns_400(self):
        appointment = self._create_appointment(
            patient=self.patient,
            doctor=self.doctor,
            appointment_date=self.tomorrow,
            appointment_time=time(17, 30),
            status_value=AppointmentStatus.CONFIRMED,
        )

        response = self.doctor_client.patch(f"/api/appointments/{appointment.id}/no-show/", format="json")
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_transition_attempt_after_no_show_returns_400(self):
        appointment = self._create_appointment(
            patient=self.patient,
            doctor=self.doctor,
            appointment_date=self.tomorrow,
            appointment_time=time(18, 0),
            status_value=AppointmentStatus.NO_SHOW,
        )

        response = self.patient_client.patch(f"/api/appointments/{appointment.id}/cancel/", format="json")
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    # CONSULTATION
    def test_consultation_doctor_files_on_checked_in_completes_appointment(self):
        appointment = self._create_appointment(
            patient=self.patient,
            doctor=self.doctor,
            appointment_date=self.tomorrow,
            appointment_time=time(18, 30),
            status_value=AppointmentStatus.CHECKED_IN,
            check_in_time=timezone.now(),
        )

        response = self.doctor_client.post(
            f"/api/appointments/{appointment.id}/consultation/",
            {
                "diagnosis": "Flu",
                "notes": "Hydrate and rest",
                "requested_tests": ["CBC", "CRP"],
                "prescription_items": [
                    {
                        "drug": "Paracetamol",
                        "dose": "500mg",
                        "duration": "5 days",
                        "instructions": "After meals",
                    }
                ],
            },
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        appointment.refresh_from_db()
        self.assertEqual(appointment.status, AppointmentStatus.COMPLETED)
        self.assertTrue(ConsultationRecord.objects.filter(appointment=appointment).exists())

    def test_consultation_non_doctor_returns_403(self):
        appointment = self._create_appointment(
            patient=self.patient,
            doctor=self.doctor,
            appointment_date=self.tomorrow,
            appointment_time=time(19, 0),
            status_value=AppointmentStatus.CHECKED_IN,
            check_in_time=timezone.now(),
        )

        response = self.receptionist_client.post(
            f"/api/appointments/{appointment.id}/consultation/",
            {"diagnosis": "Test"},
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_consultation_duplicate_returns_400(self):
        appointment = self._create_appointment(
            patient=self.patient,
            doctor=self.doctor,
            appointment_date=self.tomorrow,
            appointment_time=time(19, 30),
            status_value=AppointmentStatus.CHECKED_IN,
            check_in_time=timezone.now(),
        )

        first_response = self.doctor_client.post(
            f"/api/appointments/{appointment.id}/consultation/",
            {"diagnosis": "First diagnosis"},
            format="json",
        )
        second_response = self.doctor_client.post(
            f"/api/appointments/{appointment.id}/consultation/",
            {"diagnosis": "Second diagnosis"},
            format="json",
        )

        self.assertEqual(first_response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(second_response.status_code, status.HTTP_400_BAD_REQUEST)

    # QUEUE
    def test_queue_checked_in_appears_before_confirmed(self):
        confirmed_appointment = self._create_appointment(
            patient=self.patient,
            doctor=self.doctor,
            appointment_date=self.tomorrow,
            appointment_time=time(9, 0),
            status_value=AppointmentStatus.CONFIRMED,
        )
        checked_in_appointment = self._create_appointment(
            patient=self.patient,
            doctor=self.doctor,
            appointment_date=self.tomorrow,
            appointment_time=time(11, 0),
            status_value=AppointmentStatus.CHECKED_IN,
            check_in_time=timezone.now() - timedelta(minutes=10),
        )

        response = self.doctor_client.get(f"/api/doctors/me/queue/?date={self.tomorrow.isoformat()}")

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["items"][0]["id"], checked_in_appointment.id)
        self.assertEqual(response.data["items"][1]["id"], confirmed_appointment.id)

    def test_queue_waiting_time_minutes_is_int_for_checked_in(self):
        checked_in_appointment = self._create_appointment(
            patient=self.patient,
            doctor=self.doctor,
            appointment_date=self.tomorrow,
            appointment_time=time(12, 0),
            status_value=AppointmentStatus.CHECKED_IN,
            check_in_time=timezone.now() - timedelta(minutes=20),
        )

        response = self.doctor_client.get(f"/api/doctors/me/queue/?date={self.tomorrow.isoformat()}")

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        queue_item = next(item for item in response.data["items"] if item["id"] == checked_in_appointment.id)
        self.assertIsNotNone(queue_item["waiting_time_minutes"])
        self.assertIsInstance(queue_item["waiting_time_minutes"], int)

    # AVAILABLE SLOTS (schedule-driven)
    def test_available_slots_returns_200_and_excludes_booked_window(self):
        self._create_appointment(
            patient=self.patient,
            doctor=self.doctor,
            appointment_date=self.tomorrow,
            appointment_time=time(9, 35),
            status_value=AppointmentStatus.REQUESTED,
        )
        response = self.patient_client.get(
            "/api/slots/",
            {"doctor_id": self.doctor.id, "date": self.tomorrow.isoformat()},
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        start_times = [str(row["startTime"]).split(".")[0] for row in response.data]
        self.assertIn("09:00:00", start_times)
        self.assertNotIn("09:35:00", start_times)

    def test_available_slots_includes_slot_after_cancelled_booking(self):
        self._create_appointment(
            patient=self.patient,
            doctor=self.doctor,
            appointment_date=self.tomorrow,
            appointment_time=time(9, 35),
            status_value=AppointmentStatus.CANCELLED,
        )
        response = self.patient_client.get(
            "/api/slots/",
            {"doctor_id": self.doctor.id, "date": self.tomorrow.isoformat()},
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        start_times = [str(row["startTime"]).split(".")[0] for row in response.data]
        self.assertIn("09:35:00", start_times)

    def test_booking_with_frontend_date_and_time_payload_returns_201(self):
        response = self.patient_client.post(
            "/api/appointments/",
            {
                "doctor_id": self.doctor.id,
                "date": self.tomorrow.isoformat(),
                "time": "12:00:00",
                "reason": "Consultation",
            },
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(response.data["status"], AppointmentStatus.REQUESTED)
