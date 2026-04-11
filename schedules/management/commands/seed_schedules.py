from __future__ import annotations

from datetime import date, time, timedelta

from django.core.management.base import BaseCommand
from django.db import transaction
from django.utils import timezone

from schedules.models import DoctorSchedule, ScheduleException
from users.models import User


class Command(BaseCommand):
    help = "Seed doctor schedules and schedule exceptions for Swagger testing."

    def add_arguments(self, parser) -> None:
        parser.add_argument(
            "--reset",
            action="store_true",
            help="Delete existing schedules/exceptions for doctors before seeding.",
        )

    @transaction.atomic
    def handle(self, *args, **options) -> None:
        doctors = User.objects.filter(groups__name="Doctor").distinct()

        if not doctors.exists():
            self.stdout.write(
                self.style.WARNING(
                    "No doctors found. Run `python3 manage.py seed_data` first, then run this command again."
                )
            )
            return

        if options.get("reset"):
            DoctorSchedule.objects.filter(doctor__in=doctors).delete()
            ScheduleException.objects.filter(doctor__in=doctors).delete()

        created_or_updated_schedules = 0
        created_or_updated_exceptions = 0

        for doctor in doctors:
            created_or_updated_schedules += self._seed_weekly_schedule(doctor)
            created_or_updated_exceptions += self._seed_exceptions(doctor)

        self.stdout.write(
            self.style.SUCCESS(
                "Schedules seed completed. "
                f"Doctors: {doctors.count()}, "
                f"schedule rows touched: {created_or_updated_schedules}, "
                f"exception rows touched: {created_or_updated_exceptions}."
            )
        )

    def _seed_weekly_schedule(self, doctor: User) -> int:
        rows_touched = 0

        template = {
            0: {"start_time": time(9, 0), "end_time": time(17, 0), "session_duration_minutes": 30, "buffer_minutes": 5},
            1: {"start_time": time(9, 0), "end_time": time(17, 0), "session_duration_minutes": 30, "buffer_minutes": 5},
            2: {"start_time": time(9, 0), "end_time": time(17, 0), "session_duration_minutes": 30, "buffer_minutes": 5},
            3: {"start_time": time(9, 0), "end_time": time(17, 0), "session_duration_minutes": 30, "buffer_minutes": 5},
            4: {"start_time": time(10, 0), "end_time": time(15, 0), "session_duration_minutes": 20, "buffer_minutes": 5},
        }

        for day_of_week, defaults in template.items():
            DoctorSchedule.objects.update_or_create(
                doctor=doctor,
                day_of_week=day_of_week,
                defaults=defaults,
            )
            rows_touched += 1

        return rows_touched

    def _seed_exceptions(self, doctor: User) -> int:
        rows_touched = 0
        today: date = timezone.localdate()

        # one-off custom hours (single day)
        one_off_date = today + timedelta(days=2)
        ScheduleException.objects.update_or_create(
            doctor=doctor,
            start_date=one_off_date,
            exception_type=ScheduleException.EXCEPTION_ONE_OFF,
            defaults={
                "end_date": None,
                "custom_start_time": time(12, 0),
                "custom_end_time": time(16, 0),
                "reason": "Conference attendance (late start).",
            },
        )
        rows_touched += 1

        # day off (single day)
        day_off_date = today + timedelta(days=5)
        ScheduleException.objects.update_or_create(
            doctor=doctor,
            start_date=day_off_date,
            exception_type=ScheduleException.EXCEPTION_DAY_OFF,
            defaults={
                "end_date": None,
                "custom_start_time": None,
                "custom_end_time": None,
                "reason": "Personal leave.",
            },
        )
        rows_touched += 1

        return rows_touched
