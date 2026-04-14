from __future__ import annotations

from datetime import timedelta

from django.contrib.auth.models import Group
from django.core.management.base import BaseCommand, CommandError
from django.utils import timezone

from appointments.models import Appointment, AppointmentStatus
from users.models import User


class Command(BaseCommand):
    help = "Seed demo appointments for analytics and admin dashboard testing."

    def add_arguments(self, parser) -> None:
        parser.add_argument(
            "--reset",
            action="store_true",
            help="Delete existing appointments before seeding.",
        )

    def handle(self, *args, **options) -> None:
        if options["reset"]:
            deleted, _ = Appointment.objects.all().delete()
            self.stdout.write(self.style.WARNING(f"Deleted {deleted} existing appointment rows."))

        doctors = self._get_users_in_group("Doctor")
        patients = self._get_users_in_group("Patient")
        if not doctors:
            raise CommandError("No doctors found. Run `python manage.py seed_data` first.")
        if not patients:
            raise CommandError("No patients found. Run `python manage.py seed_data` first.")

        created = self._create_demo_appointments(doctors, patients)
        self.stdout.write(self.style.SUCCESS(f"Seeded {created} appointments."))

    def _get_users_in_group(self, group_name: str) -> list[User]:
        group = Group.objects.filter(name=group_name).first()
        if not group:
            return []
        return list(User.objects.filter(groups=group).order_by("id"))

    def _create_demo_appointments(self, doctors: list[User], patients: list[User]) -> int:
        today = timezone.localdate()
        offsets = [-45, -32, -24, -18, -12, -8, -5, -3, -1, 0, 1, 2, 4, 7, 11, 16, 23]
        times = ["09:00", "10:00", "11:00", "12:00", "14:00", "15:00", "16:00"]
        statuses = [
            AppointmentStatus.COMPLETED,
            AppointmentStatus.CONFIRMED,
            AppointmentStatus.REQUESTED,
            AppointmentStatus.CANCELLED,
            AppointmentStatus.NO_SHOW,
            AppointmentStatus.CHECKED_IN,
            AppointmentStatus.COMPLETED,
        ]

        created = 0
        index = 0
        for offset in offsets:
            appointment_date = today + timedelta(days=offset)
            for _ in range(2):
                doctor = doctors[index % len(doctors)]
                patient = patients[(index + 1) % len(patients)]
                hour, minute = times[index % len(times)].split(":")
                appointment_time = timezone.datetime(
                    year=appointment_date.year,
                    month=appointment_date.month,
                    day=appointment_date.day,
                    hour=int(hour),
                    minute=int(minute),
                ).time()
                status = statuses[index % len(statuses)]
                _, was_created = Appointment.objects.get_or_create(
                    doctor=doctor,
                    patient=patient,
                    appointment_date=appointment_date,
                    appointment_time=appointment_time,
                    defaults={
                        "status": status,
                        "reason": f"Seeded demo case #{index + 1}",
                        "session_duration_minutes": 30,
                    },
                )
                if was_created:
                    created += 1
                index += 1
        return created
