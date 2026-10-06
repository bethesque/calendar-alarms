from datetime import datetime, time, timedelta
from zoneinfo import ZoneInfo

from homeaudio.audio.settings import EventNotificationSchedule, EventNotificationSettings, NotificationRule, TimeRange
from homeaudio.vcal.cal.google_calendar import CalendarDay, CalendarSource, Event
from homeaudio.vcal.event_notifications.events import (
    get_calendar_refreshed_at,
    NotificationFinder,
    NotificationPlaytimeScheduler,
    get_event_notifications,
    update_calendar_travel_times,
)
from homeaudio.vcal.departure_time import TravelTimeCache

TIMEZONE = ZoneInfo("Australia/Melbourne")


def test_get_event_notifications_ignores_disabled_rules():
    date_string = "2026-04-06T09:00:00+10:00"
    base_time = datetime.fromisoformat(date_string)

    days = [
        {
            "date": "2026-04-06",
            "date_time": date_string,
            "timed_events": [
                {
                    "description": "",
                    "end_time": None,
                    "owner": "Beth",
                    "calendar_id": "id",
                    "recurring": False,
                    "start_time": date_string,
                    "summary": "Gym"
                }
            ],
            "whole_day_events": []
        }
    ]
    calendar_data = CalendarSource(cache_file_path="").load_data_from_any(days)

    enabled_rule = NotificationRule(summary_pattern="Gym", notification_type="announce", offset_minutes=0, enabled=True)
    disabled_rule = NotificationRule(summary_pattern="Gym", notification_type="alarm", offset_minutes=0, enabled=False)
    settings = EventNotificationSettings(notification_rules=[enabled_rule, disabled_rule])

    notifications = get_event_notifications(base_time, _scheduler(), calendar_data, settings)

    assert len(notifications) == 1
    assert notifications[0].notification_rule is enabled_rule


def test_get_calendar_refreshed_at_returns_the_stored_refreshed_at(tmp_path):
    cache_file = str(tmp_path / "calendar.json")
    refreshed_at = datetime(2026, 4, 28, 9, 0, tzinfo=TIMEZONE)
    CalendarSource(cache_file_path=cache_file, calendar_days=[], refreshed_at=refreshed_at).save_data_to_file()

    result = get_calendar_refreshed_at(CalendarSource(cache_file_path=cache_file))

    assert result == refreshed_at


def test_get_calendar_refreshed_at_returns_none_when_never_refreshed(tmp_path):
    cache_file = str(tmp_path / "calendar.json")
    CalendarSource(cache_file_path=cache_file, calendar_days=[], refreshed_at=None).save_data_to_file()

    result = get_calendar_refreshed_at(CalendarSource(cache_file_path=cache_file))

    assert result is None


def test_update_calendar_travel_times_saves_computed_departure_time_for_today_and_tomorrows_located_events(monkeypatch, tmp_path):
    now = datetime.now(TIMEZONE).replace(microsecond=0)
    today_event = Event(
        owner="Beth",
        calendar_id="id",
        summary="Dentist",
        description="#travel",
        location="123 Fake St",
        start_time=now + timedelta(hours=2),
        google_event_id="evt-1",
    )
    tomorrow_event = Event(
        owner="Beth",
        calendar_id="id",
        summary="Tomorrow's thing",
        description="#travel",
        location="456 Fake St",
        start_time=now + timedelta(days=1),
        google_event_id="evt-2",
    )
    day_after_tomorrow_event = Event(
        owner="Beth",
        calendar_id="id",
        summary="Day after tomorrow's thing",
        description="#travel",
        location="789 Fake St",
        start_time=now + timedelta(days=2),
        google_event_id="evt-3",
    )
    calendar_days = [
        CalendarDay(date=now.date(), timed_events=[today_event]),
        CalendarDay(date=(now + timedelta(days=1)).date(), timed_events=[tomorrow_event]),
        CalendarDay(date=(now + timedelta(days=2)).date(), timed_events=[day_after_tomorrow_event]),
    ]

    calendar_source = CalendarSource(cache_file_path="")
    calendar_source.calendar_days = calendar_days
    monkeypatch.setattr("homeaudio.vcal.event_notifications.events.CalendarSource", lambda: calendar_source)
    monkeypatch.setattr(calendar_source, "load_data_from_file", lambda: calendar_days)
    saved = []
    monkeypatch.setattr(calendar_source, "save_data_to_file", lambda: saved.append(True))

    fake_cache = TravelTimeCache(cache_file_path=str(tmp_path / "travel_time_cache.json"), entries={})
    monkeypatch.setattr("homeaudio.vcal.event_notifications.events.TravelTimeCache", type("_C", (), {"load": staticmethod(lambda: fake_cache)}))

    computed_departure_time = now + timedelta(hours=1)
    calls = []

    def fake_car_departure_time_for_event(event, departure_notification_settings, cache, call_now):
        calls.append(event.google_event_id)
        return computed_departure_time if event is not day_after_tomorrow_event else event.car_departure_time

    monkeypatch.setattr("homeaudio.vcal.event_notifications.events.car_departure_time_for_event", fake_car_departure_time_for_event)

    update_calendar_travel_times()

    assert calls == ["evt-1", "evt-2"]  # today's and tomorrow's events are considered, but not the day after
    assert today_event.car_departure_time == computed_departure_time
    assert tomorrow_event.car_departure_time == computed_departure_time
    assert day_after_tomorrow_event.car_departure_time is None
    assert saved == [True]


def _announce_events_at(*times: str) -> list[CalendarDay]:
    days = [
        {
            "date": "2026-04-06",
            "date_time": "2026-04-06T00:00:00+10:00",
            "timed_events": [
                {
                    "description": "#announce",
                    "end_time": None,
                    "owner": "Beth",
                    "calendar_id": "id",
                    "recurring": False,
                    "start_time": f"2026-04-06T{event_time}:00+10:00",
                    "summary": event_time,
                }
                for event_time in times
            ],
            "whole_day_events": []
        }
    ]
    return CalendarSource(cache_file_path="").load_data_from_any(days)


def test_notification_finder_includes_notifications_before_operating_hours_at_the_start():
    calendar_data = _announce_events_at("06:30", "07:03", "07:05")
    base_time = datetime.fromisoformat("2026-04-06T07:00:00+10:00")

    notifications = NotificationFinder(calendar_data, base_time, _scheduler(start=time(7, 0))).find_notification_events()

    assert [n.event.summary for n in notifications] == ["06:30", "07:03"]


def test_notification_finder_only_includes_notifications_played_at_the_base_time():
    calendar_data = _announce_events_at("06:30", "07:03", "07:05")
    base_time = datetime.fromisoformat("2026-04-06T07:00:00+10:00")

    notifications = NotificationFinder(calendar_data, base_time, _scheduler(start=time(6, 0))).find_notification_events()

    assert [n.event.summary for n in notifications] == ["07:03"]


def test_notification_finder_includes_notifications_after_operating_hours_at_the_last_tick():
    calendar_data = _announce_events_at("20:50", "20:58", "22:00")
    base_time = datetime.fromisoformat("2026-04-06T20:55:00+10:00")

    notifications = NotificationFinder(calendar_data, base_time, _scheduler(end=time(21, 0))).find_notification_events()

    assert [n.event.summary for n in notifications] == ["20:58", "22:00"]


def test_notification_finder_finds_nothing_at_a_base_time_outside_operating_hours():
    calendar_data = _announce_events_at("06:30")
    base_time = datetime.fromisoformat("2026-04-06T06:30:00+10:00")

    notifications = NotificationFinder(calendar_data, base_time, _scheduler(start=time(7, 0))).find_notification_events()

    assert notifications == []


def _scheduler(start=time(7, 0), end=time(21, 0)):
    time_range = TimeRange(start=start, end=end)
    schedule = EventNotificationSchedule(weekdays=time_range, weekends=time_range, holidays=time_range)
    return NotificationPlaytimeScheduler(TIMEZONE, schedule, [], 5)


def test_get_play_datetime_rounds_down_to_the_check_interval_within_operating_hours():
    play_datetime = _scheduler().get_play_datetime(datetime(2026, 4, 6, 9, 3, tzinfo=TIMEZONE))

    assert play_datetime == datetime(2026, 4, 6, 9, 0, tzinfo=TIMEZONE)


def test_get_play_datetime_plays_notifications_before_operating_hours_at_the_start():
    play_datetime = _scheduler().get_play_datetime(datetime(2026, 4, 6, 2, 3, tzinfo=TIMEZONE))

    assert play_datetime == datetime(2026, 4, 6, 7, 0, tzinfo=TIMEZONE)


def test_get_play_datetime_plays_notifications_after_operating_hours_at_the_last_tick():
    play_datetime = _scheduler().get_play_datetime(datetime(2026, 4, 6, 21, 0, tzinfo=TIMEZONE))

    assert play_datetime == datetime(2026, 4, 6, 20, 55, tzinfo=TIMEZONE)


def test_get_play_datetime_rounds_an_unaligned_end_down_to_the_check_interval():
    scheduler = _scheduler(end=time(21, 32))

    assert scheduler.get_play_datetime(datetime(2026, 4, 6, 21, 31, tzinfo=TIMEZONE)) == datetime(2026, 4, 6, 21, 25, tzinfo=TIMEZONE)
    assert scheduler.get_play_datetime(datetime(2026, 4, 6, 23, 0, tzinfo=TIMEZONE)) == datetime(2026, 4, 6, 21, 25, tzinfo=TIMEZONE)


def test_get_play_datetime_rounds_an_unaligned_start_down_to_the_check_interval():
    scheduler = _scheduler(start=time(6, 32))

    assert scheduler.get_play_datetime(datetime(2026, 4, 6, 6, 31, tzinfo=TIMEZONE)) == datetime(2026, 4, 6, 6, 30, tzinfo=TIMEZONE)
    assert scheduler.get_play_datetime(datetime(2026, 4, 6, 2, 0, tzinfo=TIMEZONE)) == datetime(2026, 4, 6, 6, 30, tzinfo=TIMEZONE)


def test_get_play_datetime_uses_the_local_day_for_notification_times_in_another_timezone():
    play_datetime = _scheduler().get_play_datetime(datetime(2026, 4, 5, 22, 3, tzinfo=ZoneInfo("UTC")))

    assert play_datetime == datetime(2026, 4, 6, 8, 0, tzinfo=TIMEZONE)


def test_notification_finder_warns_when_the_base_time_is_off_the_grid_within_operating_hours(caplog):
    base_time = datetime.fromisoformat("2026-04-06T09:03:00+10:00")

    NotificationFinder([], base_time, _scheduler()).find_notification_events()

    assert "not a multiple of the 5 minute check interval" in caplog.text


def test_notification_finder_does_not_warn_when_the_base_time_is_on_the_grid(caplog):
    base_time = datetime.fromisoformat("2026-04-06T09:05:00+10:00")

    NotificationFinder([], base_time, _scheduler()).find_notification_events()

    assert "not a multiple" not in caplog.text


def test_notification_finder_does_not_warn_when_the_base_time_is_off_the_grid_outside_operating_hours(caplog):
    base_time = datetime.fromisoformat("2026-04-06T06:17:00+10:00")

    NotificationFinder([], base_time, _scheduler()).find_notification_events()

    assert "not a multiple" not in caplog.text
