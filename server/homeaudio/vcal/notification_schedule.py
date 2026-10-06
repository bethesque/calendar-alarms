"""Shared scheduling helpers used by both daemon.py's notification loop and
calendar_refresh.py's refresh loop: whether a given instant falls within
EventNotificationSettings.schedule's operating hours, and when morning/school announcements are
due outside of them.
"""

from dataclasses import dataclass
from datetime import date, datetime, time, tzinfo

from homeaudio.audio.settings import (
    EventNotificationSchedule,
    MorningAnnouncementsSchedule,
    SchoolAnnouncementsSchedule,
    TimeRange,
)
from homeaudio.vcal.cal.google_calendar import CalendarDay


def round_down_to_interval(dt: datetime, interval_minutes: int) -> datetime:
    minute = (dt.minute // interval_minutes) * interval_minutes
    return dt.replace(minute=minute, second=0, microsecond=0)


def is_holiday(day: date, calendar_days: list[CalendarDay]) -> bool:
    return any(calendar_day.date == day and calendar_day.holiday for calendar_day in calendar_days)


@dataclass(frozen=True)
class DatetimeRange:
    start: datetime
    end: datetime


def event_notification_time_range_for_day(
    schedule: EventNotificationSchedule, day: date, calendar_days: list[CalendarDay], tz: tzinfo, interval_minutes: int
) -> DatetimeRange:
    if day.weekday() >= 5:  # Monday=0 ... Sunday=6
        time_range = schedule.weekends
    else:
        time_range = schedule.holidays if is_holiday(day, calendar_days) else schedule.weekdays
    return DatetimeRange(
        start=round_down_to_interval(datetime.combine(day, time_range.start, tzinfo=tz), interval_minutes),
        end=round_down_to_interval(datetime.combine(day, time_range.end, tzinfo=tz), interval_minutes),
    )


def within_event_notification_operating_hours(
    dt: datetime, schedule: EventNotificationSchedule, calendar_days: list[CalendarDay], interval_minutes: int
) -> bool:
    datetime_range = event_notification_time_range_for_day(schedule, dt.date(), calendar_days, dt.tzinfo, interval_minutes)
    return datetime_range.start <= dt < datetime_range.end


def morning_announcement_time_for_day(
    schedule: MorningAnnouncementsSchedule, day: date, calendar_days: list[CalendarDay]
) -> time | None:
    if day.weekday() >= 5:  # Monday=0 ... Sunday=6
        return schedule.weekends
    return schedule.holidays if is_holiday(day, calendar_days) else schedule.weekdays


def announcement_times_for_day(
    day: date,
    morning_schedule: MorningAnnouncementsSchedule,
    school_schedule: SchoolAnnouncementsSchedule,
    calendar_days: list[CalendarDay],
) -> list[time]:
    """Times on `day` a morning/school announcement is due outside of - and so not otherwise
    covered by - EventNotificationSettings.schedule's operating hours."""
    is_school_day = day.weekday() < 5 and not is_holiday(day, calendar_days)
    morning_time = morning_announcement_time_for_day(morning_schedule, day, calendar_days)
    school_time = school_schedule.weekdays if is_school_day else None
    return [scheduled_time for scheduled_time in (morning_time, school_time) if scheduled_time is not None]
