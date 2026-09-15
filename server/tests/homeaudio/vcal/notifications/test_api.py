import threading
from datetime import datetime, timezone

from fastapi import FastAPI
from fastapi.testclient import TestClient

from homeaudio.audio.settings import NotificationRule
from homeaudio.vcal.cal.google_calendar import Event, EventNotification, NotificationType
import homeaudio.vcal.event_notifications.api as api_module


def _client():
    app = FastAPI()
    app.include_router(api_module.AlarmRoutes().router, prefix="/alarm")
    return TestClient(app)


def test_events_page_lists_events(monkeypatch):
    event = Event(
        owner="Beth",
        calendar_id="id",
        summary="Gym session",
        description="Leg day",
        start_time=datetime(2026, 4, 28, 9, 0, tzinfo=timezone.utc),
    )
    monkeypatch.setattr(api_module, "get_all_events", lambda: [event])

    response = _client().get("/alarm/events")

    assert response.status_code == 200
    assert "Gym session" in response.text
    assert "Leg day" in response.text


def test_events_page_handles_no_events(monkeypatch):
    monkeypatch.setattr(api_module, "get_all_events", lambda: [])

    response = _client().get("/alarm/events")

    assert response.status_code == 200
    assert "No calendar events found." in response.text


def test_notifications_page_lists_notifications(monkeypatch):
    event = Event(
        owner="Beth",
        calendar_id="id",
        summary="Gym session",
        description="Leg day",
        start_time=datetime(2026, 4, 28, 9, 0, tzinfo=timezone.utc),
    )
    rule = NotificationRule(summary_pattern="gym", reminder="Remember to eat.")
    notification = EventNotification(event=event, type=NotificationType.ALARM, offset=75, notification_rule=rule)
    monkeypatch.setattr(api_module, "get_all_event_notifications", lambda: [notification])

    response = _client().get("/alarm/notifications")

    assert response.status_code == 200
    assert "Gym session" in response.text
    assert "Remember to eat." in response.text


def test_notifications_page_handles_no_notifications(monkeypatch):
    monkeypatch.setattr(api_module, "get_all_event_notifications", lambda: [])

    response = _client().get("/alarm/notifications")

    assert response.status_code == 200
    assert "No upcoming notifications." in response.text


def test_snooze_endpoint_stops_the_alarm_with_snooze_flag_set(monkeypatch):
    calls = []
    monkeypatch.setattr(api_module.AlarmHandler, "stop_alarm", lambda self, snooze=False: calls.append(snooze) or "Stopping alarm...")

    response = _client().post("/alarm/snooze")

    assert response.status_code == 202
    assert response.text == "Stopping alarm..."
    assert calls == [True]


def test_calendar_refreshed_at_endpoint_returns_the_refreshed_at_isoformat(monkeypatch):
    refreshed_at = datetime(2026, 4, 28, 9, 0, tzinfo=timezone.utc)
    monkeypatch.setattr(api_module, "get_calendar_refreshed_at", lambda: refreshed_at)

    response = _client().get("/alarm/calendar-refreshed-at")

    assert response.status_code == 200
    assert response.text == refreshed_at.isoformat()


def test_calendar_refreshed_at_endpoint_returns_empty_string_when_never_refreshed(monkeypatch):
    monkeypatch.setattr(api_module, "get_calendar_refreshed_at", lambda: None)

    response = _client().get("/alarm/calendar-refreshed-at")

    assert response.status_code == 200
    assert response.text == ""


def test_notifications_page_includes_event_json_for_the_test_button(monkeypatch):
    event = Event(
        owner="Beth",
        calendar_id="id",
        summary="Gym session",
        description="#alarm",
        start_time=datetime(2026, 4, 28, 9, 0, tzinfo=timezone.utc),
    )
    notification = EventNotification(event=event, type=NotificationType.ALARM, offset=0)
    monkeypatch.setattr(api_module, "get_all_event_notifications", lambda: [notification])

    response = _client().get("/alarm/notifications")

    assert response.status_code == 200
    assert 'data-event="' in response.text
    assert "test-notification" in response.text
    assert notification.notification_time.isoformat() in response.text


def test_test_notification_endpoint_starts_the_notification_test_and_returns_immediately(monkeypatch):
    calls = []
    monkeypatch.setattr(
        api_module.AlarmHandler,
        "test_notification",
        lambda self, event, notification_time: calls.append((event, notification_time)) or "Testing notification...",
    )

    event = {"owner": "Beth", "calendar_id": "id", "summary": "Gym session", "description": "#alarm"}
    notification_time = datetime(2026, 4, 28, 9, 0, tzinfo=timezone.utc)

    response = _client().post(
        "/alarm/test-notification",
        json={"event": event, "notification_time": notification_time.isoformat()},
    )

    assert response.status_code == 202
    assert response.text == "Testing notification..."
    assert calls == [(event, notification_time)]


def test_alarm_handler_test_notification_runs_test_notification_on_a_background_thread(monkeypatch):
    calls = []
    started = threading.Event()

    def fake_test_notification(event, notification_time):
        calls.append((event, notification_time))
        started.set()

    monkeypatch.setattr(api_module, "test_notification", fake_test_notification)

    handler = api_module.AlarmHandler()
    event = {"summary": "Gym session"}
    notification_time = datetime(2026, 4, 28, 9, 0, tzinfo=timezone.utc)

    message = handler.test_notification(event, notification_time)

    assert message == "Testing notification..."
    assert started.wait(timeout=1)
    assert calls == [(event, notification_time)]
