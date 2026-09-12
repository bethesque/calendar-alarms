from datetime import datetime, time
from zoneinfo import ZoneInfo

from homeaudio.audio.settings import (
    EventNotificationSchedule,
    MorningAnnouncementsSchedule,
    SchoolAnnouncementsSchedule,
    TimeRange,
)
from homeaudio.vcal.notification_schedule import (
    announcement_times_for_day,
    event_notification_time_range_for_day,
    within_event_notification_operating_hours,
)

TIMEZONE = ZoneInfo("Australia/Melbourne")

SCHEDULE = EventNotificationSchedule(
    weekdays=TimeRange(start=time(7, 0), end=time(21, 0)),
    weekends=TimeRange(start=time(8, 0), end=time(21, 0)),
)


def test_time_range_for_day_uses_weekdays_range_on_a_weekday():
    monday = datetime(2026, 4, 27, tzinfo=TIMEZONE).date()

    assert event_notification_time_range_for_day(SCHEDULE, monday) == SCHEDULE.weekdays


def test_time_range_for_day_uses_weekends_range_on_a_weekend():
    saturday = datetime(2026, 4, 25, tzinfo=TIMEZONE).date()

    assert event_notification_time_range_for_day(SCHEDULE, saturday) == SCHEDULE.weekends


def test_within_event_notification_operating_hours_is_true_inside_the_window():
    dt = datetime(2026, 4, 27, 12, 0, tzinfo=TIMEZONE)  # Monday midday

    assert within_event_notification_operating_hours(dt, SCHEDULE) is True


def test_within_event_notification_operating_hours_is_false_before_the_window():
    dt = datetime(2026, 4, 27, 6, 59, tzinfo=TIMEZONE)  # Monday, just before 7am

    assert within_event_notification_operating_hours(dt, SCHEDULE) is False


def test_within_event_notification_operating_hours_is_false_at_the_closing_instant():
    dt = datetime(2026, 4, 27, 21, 0, tzinfo=TIMEZONE)  # Monday, exactly 9pm - end is exclusive

    assert within_event_notification_operating_hours(dt, SCHEDULE) is False


def test_announcement_times_for_day_includes_weekday_morning_and_school_times():
    morning_schedule = MorningAnnouncementsSchedule(weekdays=time(6, 30), weekends=None)
    school_schedule = SchoolAnnouncementsSchedule(weekdays=time(6, 45))
    monday = datetime(2026, 4, 27, tzinfo=TIMEZONE).date()

    assert announcement_times_for_day(monday, morning_schedule, school_schedule) == [time(6, 30), time(6, 45)]


def test_announcement_times_for_day_omits_school_time_on_weekends():
    morning_schedule = MorningAnnouncementsSchedule(weekdays=time(6, 30), weekends=time(8, 0))
    school_schedule = SchoolAnnouncementsSchedule(weekdays=time(6, 45))
    saturday = datetime(2026, 4, 25, tzinfo=TIMEZONE).date()

    assert announcement_times_for_day(saturday, morning_schedule, school_schedule) == [time(8, 0)]


def test_announcement_times_for_day_omits_unconfigured_times():
    morning_schedule = MorningAnnouncementsSchedule(weekdays=None, weekends=None)
    school_schedule = SchoolAnnouncementsSchedule(weekdays=None)
    monday = datetime(2026, 4, 27, tzinfo=TIMEZONE).date()

    assert announcement_times_for_day(monday, morning_schedule, school_schedule) == []
