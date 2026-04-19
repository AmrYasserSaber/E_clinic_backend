import unittest.mock
from datetime import timedelta

from django.core.management import call_command
from django.core.management.base import BaseCommand
from django.utils import timezone

from appointments.models import Appointment
from slots.models import Slot
from appointments.services import (
    BookingConflictError,
    book_appointment,
    cancel_appointment,
    check_in_appointment,
    confirm_appointment,
    file_consultation,
    mark_no_show,
    reschedule_appointment,
)
from users.models import User
from rest_framework.exceptions import ValidationError


class Command(BaseCommand):
    help = "Seed the database comprehensively with realistic demo data for testing."

    def add_arguments(self, parser):
        parser.add_argument("--reset", action="store_true", help="Reset all appointments, slots, and schedules.")

    def handle(self, *args, **options):
        if options["reset"]:
            self.stdout.write("Resetting appointment and slot data...")
            Appointment.objects.all().delete()
            Slot.objects.all().delete()

        self.stdout.write("Ensuring users are seeded...")
        call_command("seed_data")

        self.stdout.write("Ensuring schedules are seeded...")
        call_command("seed_schedules", reset=options["reset"])

        self.stdout.write("Seeding comprehensive appointments...")
        self._seed_appointments()
        self.stdout.write(self.style.SUCCESS("All seed data created successfully!"))

    def _seed_appointments(self):
        doctors = list(User.objects.filter(groups__name="Doctor").order_by("id"))
        patients = list(User.objects.filter(groups__name="Patient").order_by("id"))
        receptionist = User.objects.filter(groups__name="Receptionist").first()

        if not doctors or not patients or not receptionist:
            self.stderr.write("Missing required users. Ensure seed_data successfully created them.")
            return

        today = timezone.localdate()

        scenarios = [
            {"offset": -5, "target_status": "COMPLETED", "doctor": doctors[0], "patient": patients[0], "time": "10:00"},
            {"offset": -3, "target_status": "NO_SHOW", "doctor": doctors[1], "patient": patients[1], "time": "11:00"},
            {"offset": -1, "target_status": "COMPLETED", "doctor": doctors[0], "patient": patients[2], "time": "12:00"},
            {"offset": 0, "target_status": "CHECKED_IN", "doctor": doctors[1], "patient": patients[0], "time": "14:00"},
            {"offset": 0, "target_status": "CONFIRMED", "doctor": doctors[0], "patient": patients[1], "time": "15:00"},
            {"offset": 0, "target_status": "CANCELLED", "doctor": doctors[1], "patient": patients[2], "time": "09:00"},
            {"offset": 2, "target_status": "REQUESTED", "doctor": doctors[0], "patient": patients[0], "time": "12:00"},
            {"offset": 2, "target_status": "CONFIRMED", "doctor": doctors[1], "patient": patients[1], "time": "13:00"},
            {"offset": 4, "target_status": "RESCHEDULED", "doctor": doctors[0], "patient": patients[2], "time": "10:00", "new_date_offset": 6},
            {"offset": 7, "target_status": "REQUESTED", "doctor": doctors[1], "patient": patients[0], "time": "09:00"},
        ]

        # Patch timezone.now in slot_generation so it doesn't block booking past-times for today's scenarios
        # We also need to avoid exceptions if an appointment day happens on day 5 which is day_off for doctors 
        # (schedule exceptions added in seed_schedules).
        # We skip exceptions and retry if a BookingConflictError is hit, but our times are fairly generic.

        created = 0
        past_now = timezone.now() - timedelta(days=365)
        
        for i, s in enumerate(scenarios):
            app_date = today + timedelta(days=s["offset"])
            doctor = s["doctor"]
            patient = s["patient"]
            hr, mn = map(int, s["time"].split(":"))
            app_time = timezone.datetime(year=app_date.year, month=app_date.month, day=app_date.day, hour=hr, minute=mn).time()

            try:
                with unittest.mock.patch("appointments.slot_generation.timezone.now", return_value=past_now):
                    app = book_appointment(
                        patient=patient,
                        doctor_id=doctor.id,
                        appointment_date=app_date,
                        appointment_time=app_time,
                        reason=f"Demo case #{i + 1}",
                    )
                created += 1

                if s["target_status"] in ["CONFIRMED", "CHECKED_IN", "COMPLETED", "NO_SHOW", "RESCHEDULED"]:
                    app = confirm_appointment(appointment_id=app.id, actor=receptionist)

                if s["target_status"] in ["CHECKED_IN", "COMPLETED", "NO_SHOW"]:
                    app = check_in_appointment(appointment_id=app.id, actor=receptionist)

                if s["target_status"] == "COMPLETED":
                    file_consultation(
                        appointment_id=app.id,
                        actor=doctor,
                        diagnosis="Common cold. Patient reported symptoms of fatigue and mild fever.",
                        notes="Advised rest and hydration.",
                        requested_tests=["CBC", "CRP"],
                        prescription_items=[
                            {
                                "drug": "Paracetamol 500mg",
                                "dose": "1 tablet",
                                "duration": "3 days",
                                "instructions": "Take after meals",
                            }
                        ],
                    )

                elif s["target_status"] == "NO_SHOW":
                    mark_no_show(appointment_id=app.id, actor=receptionist)

                elif s["target_status"] == "CANCELLED":
                    cancel_appointment(appointment_id=app.id, actor=receptionist)

                elif s["target_status"] == "RESCHEDULED":
                    new_date = today + timedelta(days=s["new_date_offset"])
                    with unittest.mock.patch("appointments.slot_generation.timezone.now", return_value=past_now):
                        reschedule_appointment(
                            appointment_id=app.id,
                            actor=receptionist,
                            doctor_id=doctor.id,
                            appointment_date=new_date,
                            appointment_time=app_time,
                            reason="Patient requested new date due to conflict.",
                        )

            except BookingConflictError:
                # E.g. overlaps with a schedule exception or already booked
                pass
            except ValidationError as ve:
                self.stderr.write(f"Validation error transitioning {s['target_status']}: {ve}")
            except Exception as e:
                self.stderr.write(f"Unexpected error in scenario {i}: {e}")

        self.stdout.write(f"Processed {len(scenarios)} scenarios. Successfully created {created} appointments.")
