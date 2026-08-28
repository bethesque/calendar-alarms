import signal
import threading
import time as time_module
from datetime import datetime, time, timedelta
from zoneinfo import ZoneInfo

from homeaudio.audio.settings import EventNotificationSchedule, TimeRange
from homeaudio.vcal.notifications.daemon import AlarmCheckDaemon, next_boundary, run_check

TIMEZONE = ZoneInfo("Australia/Melbourne")

SCHEDULE = EventNotificationSchedule(
    weekdays=TimeRange(start=time(7, 0), end=time(21, 0)),
    weekends=TimeRange(start=time(8, 0), end=time(21, 0)),
)


def test_next_boundary_rounds_up_to_next_five_minutes():
    now = datetime(2026, 4, 27, 7, 3, tzinfo=TIMEZONE)  # Monday

    assert next_boundary(now, SCHEDULE) == datetime(2026, 4, 27, 7, 5, tzinfo=TIMEZONE)


def test_next_boundary_lands_exactly_on_a_five_minute_mark():
    now = datetime(2026, 4, 27, 7, 5, tzinfo=TIMEZONE)  # Monday, exactly on a mark

    assert next_boundary(now, SCHEDULE) == datetime(2026, 4, 27, 7, 10, tzinfo=TIMEZONE)


def test_next_boundary_skips_to_next_days_start_hour_after_operating_window():
    now = datetime(2026, 4, 27, 20, 57, tzinfo=TIMEZONE)  # Monday, after last weekday tick

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


def test_run_check_skips_when_main_settings_disabled(monkeypatch):
    _patch_enabled(monkeypatch, main_settings_enabled=False)

    calls = []
    monkeypatch.setattr(
        "homeaudio.vcal.notifications.daemon.CalendarSource",
        lambda *a, **k: calls.append("should not be constructed"),
    )

    run_check(datetime.now(TIMEZONE))

    assert calls == []


def test_run_check_skips_when_event_notification_settings_disabled(monkeypatch):
    _patch_enabled(monkeypatch, event_notification_settings_enabled=False)

    calls = []
    monkeypatch.setattr(
        "homeaudio.vcal.notifications.daemon.CalendarSource",
        lambda *a, **k: calls.append("should not be constructed"),
    )

    run_check(datetime.now(TIMEZONE))

    assert calls == []


def test_run_check_does_not_raise_when_check_for_notifications_fails(monkeypatch):
    _patch_enabled(monkeypatch)

    class _FakeCalendarSource:
        def __init__(self, *a, **k):
            pass

        def load_data_from_file(self):
            raise RuntimeError("boom")

    monkeypatch.setattr("homeaudio.vcal.notifications.daemon.CalendarSource", _FakeCalendarSource)

    run_check(datetime.now(TIMEZONE))  # must not raise


def test_alarm_check_daemon_stops_promptly_instead_of_waiting_out_the_full_boundary(monkeypatch):
    # signal.signal() only works from the main thread; the daemon runs in a background
    # thread here so its own request_stop can be called concurrently, so stub it out.
    monkeypatch.setattr(signal, "signal", lambda *a, **k: None)

    run_check_calls = []
    monkeypatch.setattr(
        "homeaudio.vcal.notifications.daemon.run_check",
        lambda base_time: run_check_calls.append(base_time),
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
    assert len(run_check_calls) == 1  # only the startup catch-up ran before the stop was requested
