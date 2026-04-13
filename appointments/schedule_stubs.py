from __future__ import annotations

import datetime as dt
from dataclasses import dataclass

from django.db.models import Q

from schedules.models import DoctorSchedule, ScheduleException


@dataclass(frozen=True)
class WorkingDayRules:
    """Working window and slot spacing for one calendar day."""

    start_time: dt.time
    end_time: dt.time
    session_duration: dt.timedelta
    buffer: dt.timedelta


def has_schedule_exception(doctor_id: int, day: dt.date) -> bool:
    return ScheduleException.objects.filter(
        doctor_id=doctor_id,
        exception_type=ScheduleException.EXCEPTION_DAY_OFF,
        start_date__lte=day,
    ).filter(
        Q(end_date__gte=day) | Q(end_date__isnull=True, start_date=day)
    ).exists()


def get_working_window_and_rules(doctor_id: int, day: dt.date) -> WorkingDayRules | None:
    # Highest priority: explicit day off exception means no availability.
    if has_schedule_exception(doctor_id, day):
        return None

    # One-off custom working day window can override standard schedule times.
    one_off = (
        ScheduleException.objects.filter(
            doctor_id=doctor_id,
            exception_type=ScheduleException.EXCEPTION_ONE_OFF,
            start_date__lte=day,
        )
        .filter(Q(end_date__gte=day) | Q(end_date__isnull=True, start_date=day))
        .order_by("-id")
        .first()
    )

    weekday = day.weekday()  # Monday=0 ... Sunday=6
    schedule = (
        DoctorSchedule.objects.filter(doctor_id=doctor_id, day_of_week=weekday)
        .order_by("id")
        .first()
    )

    has_any_schedule = DoctorSchedule.objects.filter(doctor_id=doctor_id).exists()

    # If doctor has configured any weekly schedule rows, then only matching weekday
    # (or one-off override) is considered available.
    if has_any_schedule and schedule is None and one_off is None:
        return None

    # Backward-compatible default for doctors with no schedule rows yet.
    if not has_any_schedule and schedule is None and one_off is None:
        return WorkingDayRules(
            start_time=dt.time(9, 0),
            end_time=dt.time(17, 0),
            session_duration=dt.timedelta(minutes=30),
            buffer=dt.timedelta(minutes=5),
        )

    session_minutes = int(schedule.session_duration_minutes) if schedule is not None else 30
    buffer_minutes = int(schedule.buffer_minutes) if schedule is not None else 5

    if schedule is not None:
        start_time = schedule.start_time
        end_time = schedule.end_time
    else:
        # one_off without base weekly row
        start_time = one_off.custom_start_time
        end_time = one_off.custom_end_time

    if one_off is not None and one_off.custom_start_time and one_off.custom_end_time:
        start_time = one_off.custom_start_time
        end_time = one_off.custom_end_time

    if end_time <= start_time:
        return None
    if session_minutes <= 0 or buffer_minutes < 0:
        return None

    return WorkingDayRules(
        start_time=start_time,
        end_time=end_time,
        session_duration=dt.timedelta(minutes=session_minutes),
        buffer=dt.timedelta(minutes=buffer_minutes),
    )
