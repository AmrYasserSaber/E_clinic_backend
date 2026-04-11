from __future__ import annotations

import datetime as dt
from dataclasses import dataclass


@dataclass(frozen=True)
class WorkingDayRules:
    """Working window and slot spacing for one calendar day."""

    start_time: dt.time
    end_time: dt.time
    session_duration: dt.timedelta
    buffer: dt.timedelta


def has_schedule_exception(doctor_id: int, day: dt.date) -> bool:
    # TODO Dev 4: query ScheduleException for this doctor and date — return True on vacation/blocked days
    return False


def get_working_window_and_rules(doctor_id: int, day: dt.date) -> WorkingDayRules | None:
    # TODO Dev 4: query DoctorSchedule for weekday matching `day` and doctor_id; read start_time, end_time,
    # session_duration, buffer from the schedule row(s).
    return WorkingDayRules(
        start_time=dt.time(9, 0),
        end_time=dt.time(17, 0),
        session_duration=dt.timedelta(minutes=30),
        buffer=dt.timedelta(minutes=5),
    )
