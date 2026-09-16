from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

from homeaudio.audio.settings import EventNotificationSettings, NotificationRule
from homeaudio.vcal.cal.google_calendar import CalendarDay, CalendarSource, Event
from homeaudio.vcal.event_notifications.events import get_calendar_refreshed_at, get_event_notifications, update_calendar_travel_times
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

    notifications = get_event_notifications(base_time, 5, calendar_data, settings)

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


def test_update_calendar_travel_times_saves_computed_departure_time_for_todays_located_events(monkeypatch, tmp_path):
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
    other_day_event = Event(
        owner="Beth",
        calendar_id="id",
        summary="Tomorrow's thing",
        description="#travel",
        location="456 Fake St",
        start_time=now + timedelta(days=1),
        google_event_id="evt-2",
    )
    calendar_days = [
        CalendarDay(date=now.date(), timed_events=[today_event]),
        CalendarDay(date=(now + timedelta(days=1)).date(), timed_events=[other_day_event]),
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
        return computed_departure_time if event is today_event else event.car_departure_time

    monkeypatch.setattr("homeaudio.vcal.event_notifications.events.car_departure_time_for_event", fake_car_departure_time_for_event)

    update_calendar_travel_times()

    assert calls == ["evt-1"]  # only today's event is considered
    assert today_event.car_departure_time == computed_departure_time
    assert other_day_event.car_departure_time is None
    assert saved == [True]
