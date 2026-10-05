"""Shared scheduling helpers used by both daemon.py's notification loop and
calendar_refresh.py's refresh loop: whether a given instant falls within
EventNotificationSettings.schedule's operating hours, and when morning/school announcements are
due outside of them.
"""

from datetime import date, datetime, time

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


def event_notification_time_range_for_day(
    schedule: EventNotificationSchedule, day: date, calendar_days: list[CalendarDay]
) -> TimeRange:
    if day.weekday() >= 5:  # Monday=0 ... Sunday=6
        return schedule.weekends
    return schedule.holidays if is_holiday(day, calendar_days) else schedule.weekdays


def within_event_notification_operating_hours(
    dt: datetime, schedule: EventNotificationSchedule, calendar_days: list[CalendarDay]
) -> bool:
    time_range = event_notification_time_range_for_day(schedule, dt.date(), calendar_days)
    return time_range.start <= dt.time() < time_range.end


def event_notification_window_range(
    base_time: datetime, window: int, schedule: EventNotificationSchedule, calendar_days: list[CalendarDay]
) -> tuple[int, int]:
    """(from, to) minute offsets from `base_time` to search for event notifications, reaching back to
    midnight on the first tick of operating hours so notifications due before then aren't missed."""
    if base_time.time() != event_notification_time_range_for_day(schedule, base_time.date(), calendar_days).start:
        return (0, window)
    midnight = datetime.combine(base_time.date(), time(0), tzinfo=base_time.tzinfo)
    return (-int((base_time - midnight).total_seconds() // 60), window)


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
