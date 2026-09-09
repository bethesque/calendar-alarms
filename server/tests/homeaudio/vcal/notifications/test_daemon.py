import signal
import threading
import time as time_module
from datetime import datetime, time, timedelta
from zoneinfo import ZoneInfo

from homeaudio.audio.settings import EventNotificationSchedule, TimeRange
from homeaudio.vcal.notifications.core import NotificationFiles
from homeaudio.vcal.notifications.daemon import AlarmCheckDaemon, next_boundary, check_for_and_play_notifications, check_for_notifications, play_notification_files

TIMEZONE = ZoneInfo("Australia/Melbourne")

SCHEDULE = EventNotificationSchedule(
    weekdays=TimeRange(start=time(7, 0), end=time(21, 0)),
    weekends=TimeRange(start=time(8, 0), end=time(21, 0)),
)


def test_next_boundary_rounds_up_to_next_five_minutes(monkeypatch):
    monkeypatch.setattr("homeaudio.vcal.notifications.daemon.CHECK_WINDOW_MINUTES", 5)
    now = datetime(2026, 4, 27, 7, 3, tzinfo=TIMEZONE)  # Monday

    assert next_boundary(now, SCHEDULE) == datetime(2026, 4, 27, 7, 5, tzinfo=TIMEZONE)


def test_next_boundary_lands_exactly_on_a_five_minute_mark(monkeypatch):
    monkeypatch.setattr("homeaudio.vcal.notifications.daemon.CHECK_WINDOW_MINUTES", 5)
    now = datetime(2026, 4, 27, 7, 5, tzinfo=TIMEZONE)  # Monday, exactly on a mark

    assert next_boundary(now, SCHEDULE) == datetime(2026, 4, 27, 7, 10, tzinfo=TIMEZONE)


def test_next_boundary_skips_to_next_days_start_hour_after_operating_window(monkeypatch):
    monkeypatch.setattr("homeaudio.vcal.notifications.daemon.CHECK_WINDOW_MINUTES", 5)
    now = datetime(2026, 4, 27, 20, 57, tzinfo=TIMEZONE)  # Monday, after last weekday tick

    assert next_boundary(now, SCHEDULE) == datetime(2026, 4, 28, 7, 0, tzinfo=TIMEZONE)  # Tuesday 7am


def test_next_boundary_rounds_up_to_the_next_minute():
    now = datetime(2026, 4, 27, 7, 3, 20, tzinfo=TIMEZONE)  # Monday

    assert next_boundary(now, SCHEDULE) == datetime(2026, 4, 27, 7, 4, tzinfo=TIMEZONE)


def test_next_boundary_skips_to_next_days_start_hour_after_the_last_minute_tick():
    now = datetime(2026, 4, 27, 20, 59, 30, tzinfo=TIMEZONE)  # Monday, after the last weekday tick

    assert next_boundary(now, SCHEDULE) == datetime(2026, 4, 28, 7, 0, tzinfo=TIMEZONE)  # Tuesday 7am


def test_next_boundary_skips_forward_to_weekday_start_hour():
    now = datetime(2026, 4, 24, 6, 0, tzinfo=TIMEZONE)  # Friday, before 7am start

    assert next_boundary(now, SCHEDULE) == datetime(2026, 4, 24, 7, 0, tzinfo=TIMEZONE)


def test_next_boundary_uses_later_start_hour_on_weekends():
    now = datetime(2026, 4, 25, 6, 0, tzinfo=TIMEZONE)  # Saturday, before 8am start

    assert next_boundary(now, SCHEDULE) == datetime(2026, 4, 25, 8, 0, tzinfo=TIMEZONE)


def test_next_boundary_from_saturday_night_lands_on_sunday_8am():
    now = datetime(2026, 4, 25, 21, 0, tzinfo=TIMEZONE)  # Saturday, after last weekend tick

    assert next_boundary(now, SCHEDULE) == datetime(2026, 4, 26, 8, 0, tzinfo=TIMEZONE)  # Sunday


def test_next_boundary_respects_non_hour_aligned_start_time():
    schedule = EventNotificationSchedule(
        weekdays=TimeRange(start=time(7, 30), end=time(21, 0)),
        weekends=TimeRange(start=time(8, 0), end=time(21, 0)),
    )
    now = datetime(2026, 4, 27, 7, 0, tzinfo=TIMEZONE)  # Monday, before the 7:30 start

    assert next_boundary(now, schedule) == datetime(2026, 4, 27, 7, 30, tzinfo=TIMEZONE)


def test_next_boundary_defaults_to_live_event_notification_settings_schedule(monkeypatch):
    fake_settings = type("_S", (), {"schedule": SCHEDULE})()
    monkeypatch.setattr("homeaudio.vcal.notifications.daemon.EventNotificationSettings", lambda: fake_settings)

    now = datetime(2026, 4, 27, 6, 0, tzinfo=TIMEZONE)  # Monday, before 7am start

    assert next_boundary(now) == datetime(2026, 4, 27, 7, 0, tzinfo=TIMEZONE)


def _patch_enabled(monkeypatch, *, main_settings_enabled=True, event_notification_settings_enabled=True):
    monkeypatch.setattr(
        "homeaudio.vcal.notifications.daemon.MainSettings",
        lambda: type("_S", (), {"enabled": main_settings_enabled})(),
    )
    monkeypatch.setattr(
        "homeaudio.vcal.notifications.daemon.EventNotificationSettings",
        lambda: type("_S", (), {"enabled": event_notification_settings_enabled})(),
    )


def test_check_for_and_play_notifications_skips_when_main_settings_disabled(monkeypatch):
    _patch_enabled(monkeypatch, main_settings_enabled=False)

    calls = []
    monkeypatch.setattr(
        "homeaudio.vcal.notifications.daemon.CalendarSource",
        lambda *a, **k: calls.append("should not be constructed"),
    )

    check_for_and_play_notifications(datetime.now(TIMEZONE))

    assert calls == []


def test_check_for_and_play_notifications_skips_when_event_notification_settings_disabled(monkeypatch):
    _patch_enabled(monkeypatch, event_notification_settings_enabled=False)

    calls = []
    monkeypatch.setattr(
        "homeaudio.vcal.notifications.daemon.CalendarSource",
        lambda *a, **k: calls.append("should not be constructed"),
    )

    check_for_and_play_notifications(datetime.now(TIMEZONE))

    assert calls == []


def test_check_for_and_play_notifications_does_not_raise_when_preparing_fails(monkeypatch):
    _patch_enabled(monkeypatch)

    class _FakeCalendarSource:
        def __init__(self, *a, **k):
            pass

        def load_data_from_file(self):
            raise RuntimeError("boom")

    monkeypatch.setattr("homeaudio.vcal.notifications.daemon.CalendarSource", _FakeCalendarSource)

    check_for_and_play_notifications(datetime.now(TIMEZONE))  # must not raise


def test_alarm_check_daemon_stops_promptly_instead_of_waiting_out_the_full_boundary(monkeypatch):
    # signal.signal() only works from the main thread; the daemon runs in a background
    # thread here so its own request_stop can be called concurrently, so stub it out.
    monkeypatch.setattr(signal, "signal", lambda *a, **k: None)

    check_calls = []
    monkeypatch.setattr(
        "homeaudio.vcal.notifications.daemon.check_for_and_play_notifications",
        lambda base_time: check_calls.append(base_time),
    )
    # Far enough in the future that a real wait would still be blocked when the test checks.
    monkeypatch.setattr(
        "homeaudio.vcal.notifications.daemon.next_boundary",
        lambda now, schedule=None: now + timedelta(seconds=30),
    )

    daemon = AlarmCheckDaemon()
    thread = threading.Thread(target=daemon.run, daemon=True)
    thread.start()

    time_module.sleep(0.05)  # let it do the startup catch-up check and enter the wait
    daemon.request_stop()
    thread.join(timeout=1)

    assert not thread.is_alive(), "request_stop() should interrupt the wait immediately, not after 30s"
    assert len(check_calls) == 1  # only the startup catch-up ran before the stop was requested


def test_check_for_notifications_returns_none_when_main_settings_disabled(monkeypatch):
    _patch_enabled(monkeypatch, main_settings_enabled=False)

    assert check_for_notifications(datetime.now(TIMEZONE)) is None


def test_check_for_notifications_returns_none_when_event_notification_settings_disabled(monkeypatch):
    _patch_enabled(monkeypatch, event_notification_settings_enabled=False)

    assert check_for_notifications(datetime.now(TIMEZONE)) is None


def test_check_for_notifications_returns_none_when_preparing_raises(monkeypatch):
    _patch_enabled(monkeypatch)

    class _FakeCalendarSource:
        def __init__(self, *a, **k):
            pass

        def load_data_from_file(self):
            raise RuntimeError("boom")

    monkeypatch.setattr("homeaudio.vcal.notifications.daemon.CalendarSource", _FakeCalendarSource)

    assert check_for_notifications(datetime.now(TIMEZONE)) is None  # must not raise


def test_check_for_notifications_returns_none_when_nothing_is_due(monkeypatch):
    _patch_enabled(monkeypatch)
    monkeypatch.setattr(
        "homeaudio.vcal.notifications.daemon.CalendarSource",
        lambda *a, **k: type("_C", (), {"load_data_from_file": lambda self: None})(),
    )
    monkeypatch.setattr(
        "homeaudio.vcal.notifications.daemon.prepare_notification_files",
        lambda base_time, window, calendar_data: None,
    )

    assert check_for_notifications(datetime.now(TIMEZONE)) is None


def test_check_for_notifications_returns_the_prepared_files_when_something_is_due(monkeypatch):
    _patch_enabled(monkeypatch)
    monkeypatch.setattr(
        "homeaudio.vcal.notifications.daemon.CalendarSource",
        lambda *a, **k: type("_C", (), {"load_data_from_file": lambda self: None})(),
    )
    prepared = NotificationFiles(event_announcements_file="announce.wav")
    monkeypatch.setattr(
        "homeaudio.vcal.notifications.daemon.prepare_notification_files",
        lambda base_time, window, calendar_data: prepared,
    )

    assert check_for_notifications(datetime.now(TIMEZONE)) is prepared


def test_play_notification_files_plays_the_prepared_files(monkeypatch):
    calls = []
    monkeypatch.setattr(
        "homeaudio.vcal.notifications.daemon._play_notifications",
        lambda notification_files, scene: calls.append(notification_files),
    )

    prepared = NotificationFiles(event_announcements_file="announce.wav", event_alarms_file="alarm.wav")
    play_notification_files(prepared)

    assert calls == [prepared]


def test_play_notification_files_does_not_raise_when_playing_fails(monkeypatch):
    def raise_error(*a, **k):
        raise RuntimeError("boom")

    monkeypatch.setattr("homeaudio.vcal.notifications.daemon._play_notifications", raise_error)

    play_notification_files(NotificationFiles(event_announcements_file="announce.wav"))  # must not raise


def _daemon_with_fake_wait(monkeypatch, boundary, early_wake_seconds, wait_returns):
    """A daemon whose loop only spins as many times as `wait_returns` has entries -
    `_interruptible_wait_until` returns each value in turn, so the last one should be True
    to stop the loop and keep the test from hanging."""
    monkeypatch.setattr(signal, "signal", lambda *a, **k: None)
    monkeypatch.setattr("homeaudio.vcal.notifications.daemon.check_for_and_play_notifications", lambda base_time: None)
    monkeypatch.setattr("homeaudio.vcal.notifications.daemon.next_boundary", lambda now, schedule=None: boundary)
    monkeypatch.setattr("homeaudio.vcal.notifications.daemon.EARLY_WAKE_SECONDS", early_wake_seconds)

    daemon = AlarmCheckDaemon()
    wait_calls = []
    remaining = list(wait_returns)

    def fake_wait_until(target):
        wait_calls.append(target)
        return remaining.pop(0)

    monkeypatch.setattr(daemon, "_interruptible_wait_until", fake_wait_until)
    return daemon, wait_calls


def test_daemon_wakes_up_early_wake_seconds_before_the_boundary_to_prepare(monkeypatch):
    boundary = datetime(2026, 4, 27, 7, 5, tzinfo=TIMEZONE)
    daemon, wait_calls = _daemon_with_fake_wait(monkeypatch, boundary, early_wake_seconds=15, wait_returns=[True])

    monkeypatch.setattr("homeaudio.vcal.notifications.daemon.check_for_notifications", lambda target: None)

    daemon.run()

    assert wait_calls == [boundary - timedelta(seconds=15)]


def test_daemon_uses_the_configured_early_wake_seconds(monkeypatch):
    boundary = datetime(2026, 4, 27, 7, 5, tzinfo=TIMEZONE)
    daemon, wait_calls = _daemon_with_fake_wait(monkeypatch, boundary, early_wake_seconds=30, wait_returns=[True])

    monkeypatch.setattr("homeaudio.vcal.notifications.daemon.check_for_notifications", lambda target: None)

    daemon.run()

    assert wait_calls == [boundary - timedelta(seconds=30)]


def test_daemon_still_waits_until_the_boundary_when_nothing_is_prepared(monkeypatch):
    # Regression test: the daemon must not skip straight back to recomputing the next boundary
    # when nothing is due - doing so busy-loops for the rest of the early-wake window instead of
    # sleeping, since next_boundary() just returns the same still-upcoming target every time.
    boundary = datetime(2026, 4, 27, 7, 5, tzinfo=TIMEZONE)
    daemon, wait_calls = _daemon_with_fake_wait(monkeypatch, boundary, early_wake_seconds=15, wait_returns=[False, False, True])

    monkeypatch.setattr("homeaudio.vcal.notifications.daemon.check_for_notifications", lambda target: None)
    play_calls = []
    monkeypatch.setattr("homeaudio.vcal.notifications.daemon.play_notification_files", lambda prepared: play_calls.append(prepared))

    daemon.run()

    prepare_at = boundary - timedelta(seconds=15)
    assert wait_calls[:2] == [prepare_at, boundary]  # waited until the boundary even though nothing was due
    assert play_calls == []


def test_daemon_plays_at_the_boundary_when_something_is_prepared(monkeypatch):
    boundary = datetime(2026, 4, 27, 7, 5, tzinfo=TIMEZONE)
    daemon, wait_calls = _daemon_with_fake_wait(monkeypatch, boundary, early_wake_seconds=15, wait_returns=[False, False, True])

    prepared = ("announce.wav", None)
    monkeypatch.setattr("homeaudio.vcal.notifications.daemon.check_for_notifications", lambda target: prepared)
    play_calls = []
    monkeypatch.setattr("homeaudio.vcal.notifications.daemon.play_notification_files", lambda p: play_calls.append(p))

    daemon.run()

    prepare_at = boundary - timedelta(seconds=15)
    assert wait_calls[:2] == [prepare_at, boundary]
    assert play_calls == [prepared]
