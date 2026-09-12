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


def event_notification_time_range_for_day(schedule: EventNotificationSchedule, day: date) -> TimeRange:
    return schedule.weekdays if day.weekday() < 5 else schedule.weekends  # Monday=0 ... Sunday=6


def within_event_notification_operating_hours(dt: datetime, schedule: EventNotificationSchedule) -> bool:
    time_range = event_notification_time_range_for_day(schedule, dt.date())
    return time_range.start <= dt.time() < time_range.end


def announcement_times_for_day(
    day: date,
    morning_schedule: MorningAnnouncementsSchedule,
    school_schedule: SchoolAnnouncementsSchedule,
) -> list[time]:
    """Times on `day` a morning/school announcement is due outside of - and so not otherwise
    covered by - EventNotificationSettings.schedule's operating hours."""
    is_weekday = day.weekday() < 5  # Monday=0 ... Sunday=6
    morning_time = morning_schedule.weekdays if is_weekday else morning_schedule.weekends
    school_time = school_schedule.weekdays if is_weekday else None  # school announcements never run on weekends
    return [scheduled_time for scheduled_time in (morning_time, school_time) if scheduled_time is not None]
