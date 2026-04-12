from __future__ import annotations

import datetime as dt
from typing import TypedDict

from django.conf import settings
from django.utils import timezone

from appointments.models import Appointment
from appointments.schedule_stubs import (
    WorkingDayRules,
    get_working_window_and_rules,
    has_schedule_exception,
)
from appointments.services import EXCLUDED_CONFLICT_STATUSES


class SlotDict(TypedDict):
    doctor_id: int
    date: dt.date
    start: dt.datetime
    end: dt.datetime


def _combine(d: dt.date, t: dt.time) -> dt.datetime:
    naive = dt.datetime.combine(d, t)
    return timezone.make_aware(naive, timezone.get_current_timezone())


def _blocking_appointments_for_day(doctor_id: int, day: dt.date) -> list[Appointment]:
    return list(
        Appointment.objects.filter(
            doctor_id=doctor_id,
            appointment_date=day,
        ).exclude(status__in=EXCLUDED_CONFLICT_STATUSES)
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
    now = timezone.now()
    buffer_minutes = int(getattr(settings, "APPOINTMENT_BUFFER_MINUTES", 5))
    buf = dt.timedelta(minutes=buffer_minutes)
    blocking = _blocking_appointments_for_day(doctor_id, target_date)
    result: list[tuple[dt.datetime, dt.datetime]] = []
    for slot_start, slot_end in candidates:
        if target_date == now.date() and slot_start < now:
            continue
        # Match _doctor_has_time_conflict: requested window is session ± buffer; existing is raw session.
        req_start = slot_start - buf
        req_end = slot_end + buf
        blocked = False
        for a in blocking:
            ex_s = _combine(a.appointment_date, a.appointment_time)
            ex_e = ex_s + dt.timedelta(minutes=a.session_duration_minutes)
            if ex_s < req_end and ex_e > req_start:
                blocked = True
                break
        if blocked:
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
