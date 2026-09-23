import threading
from datetime import datetime, timezone

from fastapi import FastAPI
from fastapi.testclient import TestClient

from homeaudio.audio.settings import NotificationRule
from homeaudio.vcal.cal.google_calendar import Event
from homeaudio.vcal.event_notifications.events import EventNotification, EventNotifications, NotificationType
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


def test_notifications_page_shows_targets_when_set(monkeypatch):
    event = Event(
        owner="Beth",
        calendar_id="id",
        summary="Gym session",
        description="Leg day @kitchen @bedroom",
        start_time=datetime(2026, 4, 28, 9, 0, tzinfo=timezone.utc),
    )
    notification = EventNotification(event=event, type=NotificationType.ALARM, offset=75, targets=frozenset({"kitchen", "bedroom"}))
    monkeypatch.setattr(api_module, "get_all_event_notifications", lambda: [notification])

    response = _client().get("/alarm/notifications")

    assert response.status_code == 200
    assert "bedroom, kitchen" in response.text


def test_notifications_page_shows_all_when_no_targets_set(monkeypatch):
    event = Event(
        owner="Beth",
        calendar_id="id",
        summary="Gym session",
        description="Leg day",
        start_time=datetime(2026, 4, 28, 9, 0, tzinfo=timezone.utc),
    )
    notification = EventNotification(event=event, type=NotificationType.ALARM, offset=75, targets=None)
    monkeypatch.setattr(api_module, "get_all_event_notifications", lambda: [notification])

    response = _client().get("/alarm/notifications")

    assert response.status_code == 200
    assert "All" in response.text


def test_notifications_page_handles_no_notifications(monkeypatch):
    monkeypatch.setattr(api_module, "get_all_event_notifications", lambda: [])

    response = _client().get("/alarm/notifications")

    assert response.status_code == 200
    assert "No upcoming notifications." in response.text


def test_format_notification_for_api_maps_fields_and_rounds_play_datetime_down():
    event = Event(
        owner="Beth",
        calendar_id="id",
        summary="Gym session",
        description="Leg day",
        start_time=datetime(2026, 4, 28, 9, 7, 30, tzinfo=timezone.utc),
    )
    notification = EventNotification(event=event, type=NotificationType.ALARM, offset=0)

    result = api_module.format_notification_for_api(notification, check_interval_minutes=5)

    assert result.event.summary == "Gym session"
    assert result.type == "alarm"
    assert result.due_datetime == notification.notification_time
    assert result.play_datetime == datetime(2026, 4, 28, 9, 5, tzinfo=timezone.utc)


def test_format_notification_for_api_leaves_play_datetime_unchanged_when_already_on_a_boundary():
    event = Event(
        owner="Beth",
        calendar_id="id",
        summary="Gym session",
        description="Leg day",
        start_time=datetime(2026, 4, 28, 9, 10, tzinfo=timezone.utc),
    )
    notification = EventNotification(event=event, type=NotificationType.ANNOUNCE, offset=0)

    result = api_module.format_notification_for_api(notification, check_interval_minutes=5)

    assert result.type == "announce"
    assert result.play_datetime == notification.notification_time


def test_format_notification_for_api_shows_the_leave_for_event_summary():
    target_event = Event(
        owner="Beth",
        calendar_id="id",
        summary="Dentist",
        description="#travel10",
        start_time=datetime(2026, 4, 28, 9, 0, tzinfo=timezone.utc),
    )
    leave_event = EventNotifications(target_event).leave_for_event(datetime(2026, 4, 28, 8, 40, tzinfo=timezone.utc))
    notification = EventNotification(event=leave_event, type=NotificationType.ANNOUNCE, offset=0)

    result = api_module.format_notification_for_api(notification, check_interval_minutes=5)

    assert result.event.summary == "Leave for Dentist"


def test_notifications_endpoint_returns_json_when_accept_header_requests_it(monkeypatch):
    event = Event(
        owner="Beth",
        calendar_id="id",
        summary="Gym session",
        description="Leg day",
        start_time=datetime(2026, 4, 28, 9, 7, 30, tzinfo=timezone.utc),
    )
    notification = EventNotification(event=event, type=NotificationType.ALARM, offset=0)
    monkeypatch.setattr(api_module, "get_all_event_notifications", lambda: [notification])
    monkeypatch.setattr(api_module, "scheduled_announcement_notifications", lambda: [])
    monkeypatch.setattr(api_module, "NOTIFICATIONS_CHECK_INTERVAL_MINUTES", 5)

    response = _client().get("/alarm/notifications", headers={"Accept": "application/json"})

    assert response.status_code == 200
    assert response.json() == {
        "notifications": [
            {
                "event": {"summary": "Gym session"},
                "type": "alarm",
                "due_datetime": "2026-04-28T09:07:30Z",
                "play_datetime": "2026-04-28T09:05:00Z",
                "duration_seconds": 300,
            }
        ]
    }


def test_notifications_endpoint_includes_morning_and_school_announcements(monkeypatch):
    monkeypatch.setattr(api_module, "get_all_event_notifications", lambda: [])
    monkeypatch.setattr(
        api_module,
        "scheduled_announcement_notifications",
        lambda: [
            api_module.ScheduledAnnouncementNotification(
                summary="Morning announcements",
                due_datetime=datetime(2026, 4, 28, 7, 17, 0, tzinfo=timezone.utc),
            ),
            api_module.ScheduledAnnouncementNotification(
                summary="School announcements",
                due_datetime=datetime(2026, 4, 28, 8, 30, 0, tzinfo=timezone.utc),
            ),
        ],
    )

    response = _client().get("/alarm/notifications", headers={"Accept": "application/json"})

    assert response.status_code == 200
    assert response.json() == {
        "notifications": [
            {
                "event": {"summary": "Morning announcements"},
                "type": "announce",
                "due_datetime": "2026-04-28T07:17:00Z",
                "play_datetime": "2026-04-28T07:16:00Z",
                "duration_seconds": 300,
            },
            {
                "event": {"summary": "School announcements"},
                "type": "announce",
                "due_datetime": "2026-04-28T08:30:00Z",
                "play_datetime": "2026-04-28T08:30:00Z",
                "duration_seconds": 300,
            },
        ]
    }


def test_notifications_endpoint_returns_empty_json_list_when_no_notifications(monkeypatch):
    monkeypatch.setattr(api_module, "get_all_event_notifications", lambda: [])
    monkeypatch.setattr(api_module, "scheduled_announcement_notifications", lambda: [])

    response = _client().get("/alarm/notifications", headers={"Accept": "application/json"})

    assert response.status_code == 200
    assert response.json() == {"notifications": []}


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
