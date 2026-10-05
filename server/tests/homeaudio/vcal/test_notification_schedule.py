from datetime import datetime, time
from zoneinfo import ZoneInfo

from homeaudio.audio.settings import (
    EventNotificationSchedule,
    MorningAnnouncementsSchedule,
    SchoolAnnouncementsSchedule,
    TimeRange,
)
from homeaudio.vcal.cal.google_calendar import CalendarDay
from homeaudio.vcal.notification_schedule import (
    announcement_times_for_day,
    morning_announcement_time_for_day,
    event_notification_time_range_for_day,
    event_notification_window_range,
    round_down_to_interval,
    within_event_notification_operating_hours,
)

TIMEZONE = ZoneInfo("Australia/Melbourne")

SCHEDULE = EventNotificationSchedule(
    weekdays=TimeRange(start=time(7, 0), end=time(21, 0)),
    weekends=TimeRange(start=time(8, 0), end=time(21, 0)),
    holidays=TimeRange(start=time(9, 30), end=time(20, 0)),
)


def test_time_range_for_day_uses_weekdays_range_on_a_weekday():
    monday = datetime(2026, 4, 27, tzinfo=TIMEZONE).date()

    assert event_notification_time_range_for_day(SCHEDULE, monday, []) == SCHEDULE.weekdays


def test_time_range_for_day_uses_weekends_range_on_a_weekend():
    saturday = datetime(2026, 4, 25, tzinfo=TIMEZONE).date()

    assert event_notification_time_range_for_day(SCHEDULE, saturday, []) == SCHEDULE.weekends


def test_within_event_notification_operating_hours_is_true_inside_the_window():
    dt = datetime(2026, 4, 27, 12, 0, tzinfo=TIMEZONE)  # Monday midday

    assert within_event_notification_operating_hours(dt, SCHEDULE, []) is True


def test_within_event_notification_operating_hours_is_false_before_the_window():
    dt = datetime(2026, 4, 27, 6, 59, tzinfo=TIMEZONE)  # Monday, just before 7am

    assert within_event_notification_operating_hours(dt, SCHEDULE, []) is False


def test_within_event_notification_operating_hours_is_false_at_the_closing_instant():
    dt = datetime(2026, 4, 27, 21, 0, tzinfo=TIMEZONE)  # Monday, exactly 9pm - end is exclusive

    assert within_event_notification_operating_hours(dt, SCHEDULE, []) is False


def test_announcement_times_for_day_includes_weekday_morning_and_school_times():
    morning_schedule = MorningAnnouncementsSchedule(weekdays=time(6, 30), weekends=None)
    school_schedule = SchoolAnnouncementsSchedule(weekdays=time(6, 45))
    monday = datetime(2026, 4, 27, tzinfo=TIMEZONE).date()

    assert announcement_times_for_day(monday, morning_schedule, school_schedule, []) == [time(6, 30), time(6, 45)]


def test_announcement_times_for_day_omits_school_time_on_weekends():
    morning_schedule = MorningAnnouncementsSchedule(weekdays=time(6, 30), weekends=time(8, 0))
    school_schedule = SchoolAnnouncementsSchedule(weekdays=time(6, 45))
    saturday = datetime(2026, 4, 25, tzinfo=TIMEZONE).date()

    assert announcement_times_for_day(saturday, morning_schedule, school_schedule, []) == [time(8, 0)]


def test_announcement_times_for_day_omits_unconfigured_times():
    morning_schedule = MorningAnnouncementsSchedule(weekdays=None, weekends=None)
    school_schedule = SchoolAnnouncementsSchedule(weekdays=None)
    monday = datetime(2026, 4, 27, tzinfo=TIMEZONE).date()

    assert announcement_times_for_day(monday, morning_schedule, school_schedule, []) == []


def test_time_range_for_day_uses_holidays_range_on_a_weekday_holiday():
    monday = datetime(2026, 4, 27, tzinfo=TIMEZONE).date()

    assert event_notification_time_range_for_day(SCHEDULE, monday, [CalendarDay(date=monday, holiday=True)]) == SCHEDULE.holidays


def test_time_range_for_day_uses_weekends_range_on_a_weekend_holiday():
    saturday = datetime(2026, 5, 2, tzinfo=TIMEZONE).date()

    assert event_notification_time_range_for_day(SCHEDULE, saturday, [CalendarDay(date=saturday, holiday=True)]) == SCHEDULE.weekends


def test_time_range_for_day_uses_weekdays_range_when_a_different_day_is_a_holiday():
    monday = datetime(2026, 4, 27, tzinfo=TIMEZONE).date()
    tuesday = datetime(2026, 4, 28, tzinfo=TIMEZONE).date()

    assert event_notification_time_range_for_day(SCHEDULE, monday, [CalendarDay(date=tuesday, holiday=True)]) == SCHEDULE.weekdays


def test_within_event_notification_operating_hours_uses_the_holidays_range_on_a_holiday():
    monday_8am = datetime(2026, 4, 27, 8, 0, tzinfo=TIMEZONE)
    calendar_days = [CalendarDay(date=monday_8am.date(), holiday=True)]

    assert within_event_notification_operating_hours(monday_8am, SCHEDULE, []) is True
    assert within_event_notification_operating_hours(monday_8am, SCHEDULE, calendar_days) is False


def test_morning_announcement_time_for_day_uses_weekdays_time_on_a_weekday():
    schedule = MorningAnnouncementsSchedule(weekdays=time(7, 17), weekends=time(9, 57), holidays=time(8, 45))
    monday = datetime(2026, 4, 27, tzinfo=TIMEZONE).date()

    assert morning_announcement_time_for_day(schedule, monday, []) == time(7, 17)


def test_morning_announcement_time_for_day_uses_holidays_time_on_a_weekday_holiday():
    schedule = MorningAnnouncementsSchedule(weekdays=time(7, 17), weekends=time(9, 57), holidays=time(8, 45))
    monday = datetime(2026, 4, 27, tzinfo=TIMEZONE).date()

    assert morning_announcement_time_for_day(schedule, monday, [CalendarDay(date=monday, holiday=True)]) == time(8, 45)


def test_morning_announcement_time_for_day_uses_weekends_time_on_a_weekend_holiday():
    schedule = MorningAnnouncementsSchedule(weekdays=time(7, 17), weekends=time(9, 57), holidays=time(8, 45))
    saturday = datetime(2026, 4, 25, tzinfo=TIMEZONE).date()

    assert morning_announcement_time_for_day(schedule, saturday, [CalendarDay(date=saturday, holiday=True)]) == time(9, 57)


def test_announcement_times_for_day_uses_holiday_morning_time_and_omits_school_time_on_a_holiday():
    morning_schedule = MorningAnnouncementsSchedule(weekdays=time(6, 30), weekends=time(8, 0), holidays=time(8, 15))
    school_schedule = SchoolAnnouncementsSchedule(weekdays=time(6, 45))
    monday = datetime(2026, 4, 27, tzinfo=TIMEZONE).date()

    assert announcement_times_for_day(monday, morning_schedule, school_schedule, [CalendarDay(date=monday, holiday=True)]) == [time(8, 15)]


def test_event_notification_window_range_reaches_back_to_midnight_at_the_weekday_start():
    base_time = datetime(2026, 4, 27, 7, 0, tzinfo=TIMEZONE)  # Monday

    assert event_notification_window_range(base_time, 5, SCHEDULE, []) == (-420, 5)


def test_event_notification_window_range_reaches_back_to_midnight_at_the_weekend_start():
    base_time = datetime(2026, 4, 25, 8, 0, tzinfo=TIMEZONE)  # Saturday

    assert event_notification_window_range(base_time, 5, SCHEDULE, []) == (-480, 5)


def test_event_notification_window_range_reaches_back_to_midnight_at_the_holiday_start():
    base_time = datetime(2026, 4, 27, 9, 30, tzinfo=TIMEZONE)  # Monday

    assert event_notification_window_range(base_time, 5, SCHEDULE, [CalendarDay(date=base_time.date(), holiday=True)]) == (-570, 5)


def test_event_notification_window_range_is_unchanged_after_the_start():
    base_time = datetime(2026, 4, 27, 7, 5, tzinfo=TIMEZONE)  # Monday

    assert event_notification_window_range(base_time, 5, SCHEDULE, []) == (0, 5)


def test_event_notification_window_range_is_unchanged_at_another_days_start_time():
    base_time = datetime(2026, 4, 27, 8, 0, tzinfo=TIMEZONE)  # Monday at the weekend start time

    assert event_notification_window_range(base_time, 5, SCHEDULE, []) == (0, 5)



def test_event_notification_window_range_reaches_forward_to_midnight_at_the_last_weekday_tick():
    base_time = datetime(2026, 4, 27, 20, 55, tzinfo=TIMEZONE)  # Monday, ends 21:00

    assert event_notification_window_range(base_time, 5, SCHEDULE, []) == (0, 185)


def test_event_notification_window_range_is_unchanged_at_the_tick_before_the_last():
    base_time = datetime(2026, 4, 27, 20, 50, tzinfo=TIMEZONE)  # Monday, ends 21:00

    assert event_notification_window_range(base_time, 5, SCHEDULE, []) == (0, 5)


def test_event_notification_window_range_reaches_forward_to_midnight_when_the_end_is_off_the_grid():
    schedule = EventNotificationSchedule(weekdays=TimeRange(start=time(7, 0), end=time(21, 2)))
    base_time = datetime(2026, 4, 27, 21, 0, tzinfo=TIMEZONE)  # Monday

    assert event_notification_window_range(base_time, 5, schedule, []) == (0, 180)


def test_event_notification_window_range_reaches_forward_to_midnight_at_the_last_holiday_tick():
    base_time = datetime(2026, 4, 27, 19, 55, tzinfo=TIMEZONE)  # Monday holiday, ends 20:00

    assert event_notification_window_range(base_time, 5, SCHEDULE, [CalendarDay(date=base_time.date(), holiday=True)]) == (0, 245)


def test_event_notification_window_range_reaches_both_ways_when_the_first_tick_is_also_the_last():
    schedule = EventNotificationSchedule(weekdays=TimeRange(start=time(7, 0), end=time(7, 5)))
    base_time = datetime(2026, 4, 27, 7, 0, tzinfo=TIMEZONE)  # Monday

    assert event_notification_window_range(base_time, 5, schedule, []) == (-420, 1020)

def test_round_down_to_interval_rounds_down_to_the_nearest_boundary():
    dt = datetime(2026, 4, 28, 9, 7, 30, tzinfo=TIMEZONE)

    assert round_down_to_interval(dt, 5) == datetime(2026, 4, 28, 9, 5, tzinfo=TIMEZONE)


def test_round_down_to_interval_leaves_a_time_already_on_a_boundary_unchanged():
    dt = datetime(2026, 4, 28, 9, 10, tzinfo=TIMEZONE)

    assert round_down_to_interval(dt, 5) == dt
