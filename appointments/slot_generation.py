from __future__ import annotations

import datetime as dt
from typing import TypedDict

from django.utils import timezone

from appointments.models import Appointment
from appointments.schedule_stubs import (
    WorkingDayRules,
    get_working_window_and_rules,
    has_schedule_exception,
)


class SlotDict(TypedDict):
    doctor_id: int
    date: dt.date
    start: dt.datetime
    end: dt.datetime


def _combine(d: dt.date, t: dt.time) -> dt.datetime:
    naive = dt.datetime.combine(d, t)
    return timezone.make_aware(naive, timezone.get_current_timezone())


def _intervals_overlap(
    a_start: dt.datetime,
    a_end: dt.datetime,
    b_start: dt.datetime,
    b_end: dt.datetime,
) -> bool:
    return a_start < b_end and b_start < a_end

# TODO: need review - this is a bit complex and may have edge cases. Consider simplifying by just checking if the slot start time overlaps with any existing appointment, since we assume fixed session durations.
def _blocking_appointments_for_day(
    doctor_id: int, day: dt.date, tz
) -> list[Appointment]:
    return list(
        Appointment.objects.filter(
            doctor_id=doctor_id,
            date=day,
        ).exclude(
            status__in=[Appointment.Status.CANCELLED, Appointment.Status.NO_SHOW],
        )
    )


def iter_candidate_slots(
    target_date: dt.date,
    rules: WorkingDayRules,
) -> list[tuple[dt.datetime, dt.datetime]]:
    window_start = _combine(target_date, rules.start_time)
    window_end = _combine(target_date, rules.end_time)

    if rules.session_duration <= dt.timedelta(0):
        raise ValueError("session_duration must be > 0")
    if rules.buffer < dt.timedelta(0):
        raise ValueError("buffer must be >= 0")

    step = rules.session_duration + rules.buffer

    if step <= dt.timedelta(0):
        raise ValueError("session_duration + buffer must be > 0")

    out: list[tuple[dt.datetime, dt.datetime]] = []
    t = window_start

    while True:
        effective_end = t + rules.session_duration
        if effective_end > window_end:
            break
        out.append((t, effective_end))
        t += step
    return out


def filter_booked_and_past(
    doctor_id: int,
    target_date: dt.date,
    candidates: list[tuple[dt.datetime, dt.datetime]],
) -> list[tuple[dt.datetime, dt.datetime]]:
    tz = timezone.get_current_timezone()
    now = timezone.now()
    blocking = _blocking_appointments_for_day(doctor_id, target_date, tz)
    result: list[tuple[dt.datetime, dt.datetime]] = []
    for slot_start, slot_end in candidates:
        if target_date == now.date() and slot_start < now:
            continue
        if any(
            _intervals_overlap(
                slot_start,
                slot_end,
                _combine(a.date, a.time),
                _combine(a.date, a.time) + dt.timedelta(minutes=a.session_duration),
            )
            for a in blocking
        ):
            continue
        result.append((slot_start, slot_end))
    result.sort(key=lambda x: x[0])
    return result


def iter_available_slots(doctor_id: int, target_date: dt.date) -> list[SlotDict]:
    if has_schedule_exception(doctor_id, target_date):
        return []
    rules = get_working_window_and_rules(doctor_id, target_date)
    if rules is None:
        return []
    candidates = iter_candidate_slots(target_date, rules)
    filtered = filter_booked_and_past(doctor_id, target_date, candidates)
    return [
        {
            "doctor_id": doctor_id,
            "date": target_date,
            "start": s,
            "end": e,
        }
        for s, e in filtered
    ]
