import threading
from datetime import datetime, time, timedelta
from zoneinfo import ZoneInfo

from homeaudio.audio.settings import (
    EventNotificationSchedule,
    MorningAnnouncementsSchedule,
    SchoolAnnouncementsSchedule,
    TimeRange,
)
from homeaudio.vcal.calendar_refresh import (
    REFRESH_INTERVAL_MINUTES,
    REFRESH_OFFSET_SECONDS,
    CalendarRefreshLoop,
    next_refresh_boundary,
    refresh_calendar,
    _wake_window_for_day,
)

TIMEZONE = ZoneInfo("Australia/Melbourne")

SCHEDULE = EventNotificationSchedule(
    weekdays=TimeRange(start=time(7, 0), end=time(21, 0)),
    weekends=TimeRange(start=time(8, 0), end=time(21, 0)),
)

# Schedules with no configured times, so tests that aren't exercising morning/school
# announcements aren't affected by them (and don't need to know their default schedule).
NO_MORNING_SCHEDULE = MorningAnnouncementsSchedule(weekdays=None, weekends=None)
NO_SCHOOL_SCHEDULE = SchoolAnnouncementsSchedule(weekdays=None)

# A MAX_SLEEP_SECONDS large enough that tests exercising multi-hour/overnight gaps aren't
# affected by the cap - it's tested on its own terms separately.
UNCAPPED_MAX_SLEEP_SECONDS = 60 * 60 * 24 * 7


def test_wake_window_for_day_opens_a_lead_buffer_before_the_base_schedule_with_no_announcements():
    monday = datetime(2026, 4, 27, tzinfo=TIMEZONE).date()

    window = _wake_window_for_day(monday, SCHEDULE, NO_MORNING_SCHEDULE, NO_SCHOOL_SCHEDULE)

    assert window == TimeRange(start=time(6, 45), end=SCHEDULE.weekdays.end)


def test_wake_window_for_day_opens_a_lead_buffer_before_an_earlier_announcement():
    # The whole point of the buffer: without it, the day's first refresh would land at 6:30,
    # the exact same instant as the notification loop's own prepare tick for that announcement.
    morning_schedule = MorningAnnouncementsSchedule(weekdays=time(6, 30), weekends=None)
    monday = datetime(2026, 4, 27, tzinfo=TIMEZONE).date()

    window = _wake_window_for_day(monday, SCHEDULE, morning_schedule, NO_SCHOOL_SCHEDULE)

    assert window == TimeRange(start=time(6, 30 - 3 * REFRESH_INTERVAL_MINUTES), end=SCHEDULE.weekdays.end)


def test_wake_window_for_day_widens_the_end_for_a_later_announcement():
    # A later announcement just needs the window kept open through it - the regular
    # REFRESH_INTERVAL_MINUTES cadence already keeps data fresh well ahead of it by the time it
    # arrives, unlike the day's very first refresh, which has nothing preceding it.
    morning_schedule = MorningAnnouncementsSchedule(weekdays=time(22, 0), weekends=None)
    monday = datetime(2026, 4, 27, tzinfo=TIMEZONE).date()

    window = _wake_window_for_day(monday, SCHEDULE, morning_schedule, NO_SCHOOL_SCHEDULE)

    assert window == TimeRange(start=time(6, 45), end=time(22, 0))


def test_next_refresh_boundary_rounds_up_to_the_offset_within_the_current_interval():
    base = datetime(2026, 4, 27, 7, 0, tzinfo=TIMEZONE)  # Monday
    now = base + timedelta(minutes=1)  # before this bucket's own offset instant

    assert next_refresh_boundary(now, SCHEDULE, NO_MORNING_SCHEDULE, NO_SCHOOL_SCHEDULE) == base + timedelta(
        seconds=REFRESH_OFFSET_SECONDS
    )


def test_next_refresh_boundary_moves_to_the_next_interval_once_the_offset_has_passed():
    base = datetime(2026, 4, 27, 7, 0, tzinfo=TIMEZONE)  # Monday
    now = base + timedelta(minutes=4)  # past this bucket's own offset instant

    assert next_refresh_boundary(now, SCHEDULE, NO_MORNING_SCHEDULE, NO_SCHOOL_SCHEDULE) == base + timedelta(
        minutes=REFRESH_INTERVAL_MINUTES, seconds=REFRESH_OFFSET_SECONDS
    )


def test_next_refresh_boundary_lands_exactly_on_the_offset_instant():
    base = datetime(2026, 4, 27, 7, 0, tzinfo=TIMEZONE)  # Monday
    now = base + timedelta(seconds=REFRESH_OFFSET_SECONDS)  # exactly on this bucket's offset instant

    assert next_refresh_boundary(now, SCHEDULE, NO_MORNING_SCHEDULE, NO_SCHOOL_SCHEDULE) == base + timedelta(
        minutes=REFRESH_INTERVAL_MINUTES, seconds=REFRESH_OFFSET_SECONDS
    )


def test_next_refresh_boundary_never_lands_on_the_notification_loops_own_tick_instants():
    # Regression test: the whole point of the offset is to avoid the :45 prepare / :00 play
    # instants daemon.next_boundary() uses, since both loops share one CPU core on a Pi Zero W.
    now = datetime(2026, 4, 27, 7, 0, tzinfo=TIMEZONE)  # Monday

    boundary = next_refresh_boundary(now, SCHEDULE, NO_MORNING_SCHEDULE, NO_SCHOOL_SCHEDULE)

    assert boundary.minute % REFRESH_INTERVAL_MINUTES == REFRESH_OFFSET_SECONDS // 60
    assert boundary.second == REFRESH_OFFSET_SECONDS % 60


def test_next_refresh_boundary_skips_forward_to_the_lead_adjusted_window_start():
    now = datetime(2026, 4, 24, 6, 0, tzinfo=TIMEZONE)  # Friday, before 7am start
    window_start = datetime(2026, 4, 24, 7, 0, tzinfo=TIMEZONE) - timedelta(minutes=3 * REFRESH_INTERVAL_MINUTES)

    assert next_refresh_boundary(now, SCHEDULE, NO_MORNING_SCHEDULE, NO_SCHOOL_SCHEDULE) == window_start + timedelta(
        seconds=REFRESH_OFFSET_SECONDS
    )


def test_next_refresh_boundary_skips_to_next_days_start_after_operating_window(monkeypatch):
    monkeypatch.setattr("homeaudio.vcal.calendar_refresh.MAX_SLEEP_SECONDS", UNCAPPED_MAX_SLEEP_SECONDS)
    # Monday, exactly the last in-window tick - the next one falls past the 9pm close.
    now = datetime(2026, 4, 27, 20, 55, tzinfo=TIMEZONE) + timedelta(seconds=REFRESH_OFFSET_SECONDS)
    next_day_start = datetime(2026, 4, 28, 7, 0, tzinfo=TIMEZONE) - timedelta(minutes=3 * REFRESH_INTERVAL_MINUTES)

    assert next_refresh_boundary(
        now, SCHEDULE, NO_MORNING_SCHEDULE, NO_SCHOOL_SCHEDULE
    ) == next_day_start + timedelta(seconds=REFRESH_OFFSET_SECONDS)  # Tuesday, lead-adjusted 7am


def test_next_refresh_boundary_uses_later_start_hour_on_weekends(monkeypatch):
    monkeypatch.setattr("homeaudio.vcal.calendar_refresh.MAX_SLEEP_SECONDS", UNCAPPED_MAX_SLEEP_SECONDS)
    now = datetime(2026, 4, 25, 6, 0, tzinfo=TIMEZONE)  # Saturday, before 8am start
    window_start = datetime(2026, 4, 25, 8, 0, tzinfo=TIMEZONE) - timedelta(minutes=3 * REFRESH_INTERVAL_MINUTES)

    assert next_refresh_boundary(now, SCHEDULE, NO_MORNING_SCHEDULE, NO_SCHOOL_SCHEDULE) == window_start + timedelta(
        seconds=REFRESH_OFFSET_SECONDS
    )


def test_next_refresh_boundary_caps_a_long_gap_at_max_sleep_seconds(monkeypatch):
    monkeypatch.setattr("homeaudio.vcal.calendar_refresh.MAX_SLEEP_SECONDS", 3600)
    now = datetime(2026, 4, 27, 22, 0, tzinfo=TIMEZONE)  # Monday, ~9 hours before Tuesday 7am

    assert next_refresh_boundary(now, SCHEDULE, NO_MORNING_SCHEDULE, NO_SCHOOL_SCHEDULE) == now + timedelta(
        seconds=3600
    )


def test_next_refresh_boundary_defaults_to_live_settings(monkeypatch):
    fake_schedule_settings = type("_S", (), {"schedule": SCHEDULE})()
    monkeypatch.setattr("homeaudio.vcal.calendar_refresh.EventNotificationSettings", lambda: fake_schedule_settings)
    monkeypatch.setattr(
        "homeaudio.vcal.calendar_refresh.MorningAnnouncementsSettings",
        lambda: type("_S", (), {"schedule": NO_MORNING_SCHEDULE})(),
    )
    monkeypatch.setattr(
        "homeaudio.vcal.calendar_refresh.SchoolAnnouncementsSettings",
        lambda: type("_S", (), {"schedule": NO_SCHOOL_SCHEDULE})(),
    )

    now = datetime(2026, 4, 27, 6, 0, tzinfo=TIMEZONE)  # Monday, before 7am start
    window_start = datetime(2026, 4, 27, 7, 0, tzinfo=TIMEZONE) - timedelta(minutes=3 * REFRESH_INTERVAL_MINUTES)

    assert next_refresh_boundary(now) == window_start + timedelta(seconds=REFRESH_OFFSET_SECONDS)


def test_next_refresh_boundary_wakes_with_a_lead_buffer_for_an_earlier_morning_announcement():
    # The day's first refresh must land a few minutes before the announcement, not at the same
    # instant as the notification loop's own prepare tick for it.
    morning_schedule = MorningAnnouncementsSchedule(weekdays=time(6, 30), weekends=None)
    now = datetime(2026, 4, 27, 6, 0, tzinfo=TIMEZONE)  # Monday, before the 6:30 announcement and 7am start
    window_start = datetime(2026, 4, 27, 6, 30, tzinfo=TIMEZONE) - timedelta(minutes=3 * REFRESH_INTERVAL_MINUTES)

    assert next_refresh_boundary(now, SCHEDULE, morning_schedule, NO_SCHOOL_SCHEDULE) == window_start + timedelta(
        seconds=REFRESH_OFFSET_SECONDS
    )


def test_next_refresh_boundary_wakes_with_a_lead_buffer_for_an_earlier_school_announcement():
    school_schedule = SchoolAnnouncementsSchedule(weekdays=time(6, 45))
    now = datetime(2026, 4, 27, 6, 0, tzinfo=TIMEZONE)  # Monday, before the 6:45 announcement and 7am start
    window_start = datetime(2026, 4, 27, 6, 45, tzinfo=TIMEZONE) - timedelta(minutes=3 * REFRESH_INTERVAL_MINUTES)

    assert next_refresh_boundary(now, SCHEDULE, NO_MORNING_SCHEDULE, school_schedule) == window_start + timedelta(
        seconds=REFRESH_OFFSET_SECONDS
    )


def test_next_refresh_boundary_applies_the_lead_buffer_to_the_earliest_of_several_announcements():
    morning_schedule = MorningAnnouncementsSchedule(weekdays=time(6, 45), weekends=None)
    school_schedule = SchoolAnnouncementsSchedule(weekdays=time(6, 30))
    now = datetime(2026, 4, 27, 6, 0, tzinfo=TIMEZONE)  # Monday, before both school (6:30) and morning (6:45)
    window_start = datetime(2026, 4, 27, 6, 30, tzinfo=TIMEZONE) - timedelta(minutes=3 * REFRESH_INTERVAL_MINUTES)

    assert next_refresh_boundary(now, SCHEDULE, morning_schedule, school_schedule) == window_start + timedelta(
        seconds=REFRESH_OFFSET_SECONDS
    )


def test_next_refresh_boundary_does_not_double_tick_right_after_jumping_into_the_window():
    # Regression test: landing exactly on window.start used to produce a spurious extra tick only
    # REFRESH_OFFSET_SECONDS before the next regularly-scheduled one.
    morning_schedule = MorningAnnouncementsSchedule(weekdays=time(6, 30), weekends=None)
    now = datetime(2026, 4, 27, 6, 0, tzinfo=TIMEZONE)  # Monday

    first_tick = next_refresh_boundary(now, SCHEDULE, morning_schedule, NO_SCHOOL_SCHEDULE)
    second_tick = next_refresh_boundary(first_tick, SCHEDULE, morning_schedule, NO_SCHOOL_SCHEDULE)

    assert second_tick - first_tick == timedelta(minutes=REFRESH_INTERVAL_MINUTES)


def test_next_refresh_boundary_widens_the_window_to_include_a_later_announcement():
    morning_schedule = MorningAnnouncementsSchedule(weekdays=time(22, 0), weekends=None)
    base = datetime(2026, 4, 27, 21, 0, tzinfo=TIMEZONE)  # Monday, exactly the normal 9pm close

    # Regular cadence continues past the normal close, since the window now extends to 22:00.
    assert next_refresh_boundary(base, SCHEDULE, morning_schedule, NO_SCHOOL_SCHEDULE) == base + timedelta(
        seconds=REFRESH_OFFSET_SECONDS
    )


def test_next_refresh_boundary_skips_to_next_day_once_the_widened_window_closes(monkeypatch):
    monkeypatch.setattr("homeaudio.vcal.calendar_refresh.MAX_SLEEP_SECONDS", UNCAPPED_MAX_SLEEP_SECONDS)
    morning_schedule = MorningAnnouncementsSchedule(weekdays=time(22, 0), weekends=None)
    now = datetime(2026, 4, 27, 22, 0, tzinfo=TIMEZONE)  # Monday, exactly the widened close (end is exclusive)
    next_day_start = datetime(2026, 4, 28, 7, 0, tzinfo=TIMEZONE) - timedelta(minutes=3 * REFRESH_INTERVAL_MINUTES)

    assert next_refresh_boundary(
        now, SCHEDULE, morning_schedule, NO_SCHOOL_SCHEDULE
    ) == next_day_start + timedelta(
        seconds=REFRESH_OFFSET_SECONDS
    )  # Tuesday, lead-adjusted 7am - the following weekday's start is unaffected by Monday's widened end


def test_next_refresh_boundary_ignores_school_announcement_schedule_on_weekends(monkeypatch):
    monkeypatch.setattr("homeaudio.vcal.calendar_refresh.MAX_SLEEP_SECONDS", UNCAPPED_MAX_SLEEP_SECONDS)
    school_schedule = SchoolAnnouncementsSchedule(weekdays=time(6, 30))
    now = datetime(2026, 4, 25, 6, 0, tzinfo=TIMEZONE)  # Saturday, before the weekday-only school time and 8am start
    window_start = datetime(2026, 4, 25, 8, 0, tzinfo=TIMEZONE) - timedelta(minutes=3 * REFRESH_INTERVAL_MINUTES)

    assert next_refresh_boundary(
        now, SCHEDULE, NO_MORNING_SCHEDULE, school_schedule
    ) == window_start + timedelta(seconds=REFRESH_OFFSET_SECONDS)


def test_refresh_calendar_fetches_and_saves(monkeypatch):
    calls = []
    monkeypatch.setattr(
        "homeaudio.vcal.calendar_refresh.fetch_and_save_calendar_data", lambda: calls.append("refreshed")
    )

    refresh_calendar(datetime.now(TIMEZONE))

    assert calls == ["refreshed"]


def test_refresh_calendar_does_not_raise_when_fetching_fails(monkeypatch):
    def raise_error():
        raise RuntimeError("boom")

    monkeypatch.setattr("homeaudio.vcal.calendar_refresh.fetch_and_save_calendar_data", raise_error)

    refresh_calendar(datetime.now(TIMEZONE))  # must not raise


def test_calendar_refresh_loop_start_returns_a_named_daemon_thread():
    stop_event = threading.Event()
    stop_event.set()  # so _run exits immediately if it gets scheduled before join(), skipping the startup refresh

    thread = CalendarRefreshLoop(stop_event).start()

    assert thread.daemon is True
    assert thread.name == "calendar-refresh"
    thread.join(timeout=1)
    assert not thread.is_alive()


def test_calendar_refresh_loop_refreshes_immediately_on_start(monkeypatch):
    # So calendar.json isn't left stale for however long until the first regular boundary.
    monkeypatch.setattr(
        "homeaudio.vcal.calendar_refresh.next_refresh_boundary",
        lambda now, schedule=None, morning_schedule=None, school_schedule=None: now + timedelta(hours=1),
    )
    refresh_calls = []
    monkeypatch.setattr(
        "homeaudio.vcal.calendar_refresh.refresh_calendar",
        lambda base_time: refresh_calls.append(base_time),
    )

    stop_event = threading.Event()
    thread = CalendarRefreshLoop(stop_event).start()

    stop_event.set()
    thread.join(timeout=1)

    assert not thread.is_alive()
    assert len(refresh_calls) == 1  # the startup refresh, not the (far-off) first boundary


def test_calendar_refresh_loop_stops_promptly_instead_of_waiting_out_the_full_boundary(monkeypatch):
    # Far enough in the future that a real wait would still be blocked when the test checks.
    monkeypatch.setattr(
        "homeaudio.vcal.calendar_refresh.next_refresh_boundary",
        lambda now, schedule=None, morning_schedule=None, school_schedule=None: now + timedelta(seconds=30),
    )
    started = threading.Event()  # signals the startup refresh landed, so stopping below is deterministic
    refresh_calls = []

    def fake_refresh_calendar(base_time):
        refresh_calls.append(base_time)
        started.set()

    monkeypatch.setattr("homeaudio.vcal.calendar_refresh.refresh_calendar", fake_refresh_calendar)

    stop_event = threading.Event()
    thread = CalendarRefreshLoop(stop_event).start()

    assert started.wait(timeout=1)
    stop_event.set()
    thread.join(timeout=1)

    assert not thread.is_alive()
    assert len(refresh_calls) == 1  # only the startup refresh - the 30s boundary never arrived
