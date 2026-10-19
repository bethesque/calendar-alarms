import threading
from datetime import date, datetime, timezone
from types import SimpleNamespace

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from homeaudio.audio.settings import NotificationRule
from homeaudio.vcal.cal.google_calendar import CalendarDay, CalendarDayList, WholeDayEvent, Event
from homeaudio.vcal.event_notifications.events import EventNotification, EventNotifications, NotificationPlaytimeScheduler, NotificationSource, NotificationType
from homeaudio.audio.settings import EventNotificationSchedule
from homeaudio.vcal.event_notifications.scheduled_announcements import ScheduledAnnouncementType
import homeaudio.vcal.api as api_module
import homeaudio.vcal.cal.google_calendar as google_calendar
from homeaudio.vcal.cal.google_calendar import calendar_data_lock


@pytest.fixture(autouse=True)
def calendar_lock_file(monkeypatch, tmp_path):
    lock_file_path = str(tmp_path / "calendar.json.lock")
    monkeypatch.setattr(google_calendar, "LOCK_FILE", lock_file_path)
    return lock_file_path


@pytest.fixture(autouse=True)
def no_calendar_events(monkeypatch):
    monkeypatch.setattr(api_module, "get_calendar_days", lambda: CalendarDayList())
    monkeypatch.setattr(api_module, "scheduled_announcement_notifications", lambda: [])


def _client():
    app = FastAPI()
    app.include_router(api_module.AlarmRoutes().router, prefix="/alarm")
    return TestClient(app)


def test_events_page_lists_events_under_their_day(monkeypatch):
    timed_event = Event(
        owner="Beth",
        calendar_id="id",
        summary="Gym session",
        description="Leg day",
        start_time=datetime(2026, 4, 28, 9, 0, tzinfo=timezone.utc),
    )
    whole_day_event = WholeDayEvent(owner="Beth", calendar_id="id", summary="Public holiday", description="")
    days = CalendarDayList([
        CalendarDay(date=date(2026, 4, 27)),
        CalendarDay(date=date(2026, 4, 28), whole_day_events=[whole_day_event], timed_events=[timed_event]),
        CalendarDay(date=date(2026, 4, 29), whole_day_events=[whole_day_event]),
    ])
    monkeypatch.setattr(api_module, "get_calendar_days", lambda: days)
    monkeypatch.setattr(api_module, "get_all_event_notifications", lambda: [])

    response = _client().get("/alarm/notifications")

    assert response.status_code == 200
    assert "Mon 27 Apr" not in response.text
    tuesday = response.text.index("Tue 28 Apr")
    holiday = response.text.index("Public holiday")
    gym = response.text.index("Gym session")
    wednesday = response.text.index("Wed 29 Apr")
    assert tuesday < holiday < gym < wednesday
    assert response.text.index("Public holiday", wednesday) > wednesday
    assert "Leg day" in response.text


def test_events_page_handles_no_events(monkeypatch):
    monkeypatch.setattr(api_module, "get_calendar_days", lambda: CalendarDayList())
    monkeypatch.setattr(api_module, "get_all_event_notifications", lambda: [])

    response = _client().get("/alarm/notifications")

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
    notification = EventNotification(event=event, type=NotificationType.ALARM, offset=75, notification_rule=rule, source=NotificationSource.NOTIFICATION_RULE)
    notification.play_datetime = notification.notification_time
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
    notification = EventNotification(event=event, type=NotificationType.ALARM, offset=75, targets=frozenset({"kitchen", "bedroom"}), source=NotificationSource.ALARM_DESCRIPTION_TAG)
    notification.play_datetime = notification.notification_time
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
    notification = EventNotification(event=event, type=NotificationType.ALARM, offset=75, targets=None, source=NotificationSource.ALARM_DESCRIPTION_TAG)
    notification.play_datetime = notification.notification_time
    monkeypatch.setattr(api_module, "get_all_event_notifications", lambda: [notification])

    response = _client().get("/alarm/notifications")

    assert response.status_code == 200
    assert "All" in response.text


def test_notifications_page_includes_morning_and_school_announcements_sorted_by_time(monkeypatch):
    event = Event(
        owner="Beth",
        calendar_id="id",
        summary="Gym session",
        description="Leg day",
        start_time=datetime(2026, 4, 28, 8, 0, tzinfo=timezone.utc),
    )
    notification = EventNotification(event=event, type=NotificationType.ALARM, offset=0, source=NotificationSource.ALARM_DESCRIPTION_TAG)
    notification.play_datetime = notification.notification_time
    monkeypatch.setattr(api_module, "get_all_event_notifications", lambda: [notification])
    monkeypatch.setattr(
        api_module,
        "scheduled_announcement_notifications",
        lambda: [
            api_module.ScheduledAnnouncementNotification(
                summary="Morning announcements",
                type=ScheduledAnnouncementType.MORNING_ANNOUNCEMENTS,
                due_datetime=datetime(2026, 4, 28, 7, 15, tzinfo=timezone.utc),
            ),
            api_module.ScheduledAnnouncementNotification(
                summary="School announcements",
                type=ScheduledAnnouncementType.SCHOOL_ANNOUNCEMENTS,
                due_datetime=datetime(2026, 4, 28, 8, 30, tzinfo=timezone.utc),
            ),
        ],
    )

    response = _client().get("/alarm/notifications")

    assert response.status_code == 200
    morning = response.text.index("MORNING ANNOUNCEMENTS")
    gym = response.text.index("Gym session")
    school = response.text.index("SCHOOL ANNOUNCEMENTS")
    assert morning < gym < school
    assert "Tue, 28 Apr 26<br></span>07:15 AM" in response.text
    assert 'data-path="/alarm/morning-announcements"' in response.text
    assert 'data-base-time="2026-04-28T07:15:00+00:00"' in response.text
    assert 'data-path="/alarm/school-announcements"' in response.text


def _gym_alarm_playing_at(play_datetime):
    event = Event(
        owner="Beth",
        calendar_id="id",
        summary="Gym session",
        description="#alarm",
        start_time=datetime(2026, 4, 28, 22, 0, tzinfo=timezone.utc),
    )
    notification = EventNotification(event=event, type=NotificationType.ALARM, offset=0, source=NotificationSource.ALARM_DESCRIPTION_TAG)
    notification.play_datetime = play_datetime
    return notification


def test_notifications_page_shows_the_play_time_with_a_warning_when_it_differs_from_the_notification_time(monkeypatch):
    notification = _gym_alarm_playing_at(datetime(2026, 4, 28, 20, 55, tzinfo=timezone.utc))
    monkeypatch.setattr(api_module, "get_all_event_notifications", lambda: [notification])

    response = _client().get("/alarm/notifications")

    assert response.status_code == 200
    assert "Tue, 28 Apr 26<br></span>08:55 PM" in response.text
    assert 'title="Changed from 10:00 PM due to operation hours or to match notification check window"' in response.text
    assert "⚠︎" in response.text


def test_notifications_page_shows_no_warning_when_the_play_time_matches_the_notification_time(monkeypatch):
    notification = _gym_alarm_playing_at(datetime(2026, 4, 28, 22, 0, tzinfo=timezone.utc))
    monkeypatch.setattr(api_module, "get_all_event_notifications", lambda: [notification])

    response = _client().get("/alarm/notifications")

    assert response.status_code == 200
    assert "Tue, 28 Apr 26<br></span>10:00 PM" in response.text
    assert "⚠︎" not in response.text


def test_notifications_page_handles_no_notifications(monkeypatch):
    monkeypatch.setattr(api_module, "get_all_event_notifications", lambda: [])

    response = _client().get("/alarm/notifications")

    assert response.status_code == 200
    assert "No upcoming notifications." in response.text


def test_format_notification_for_api_maps_fields_and_uses_the_notifications_play_datetime():
    event = Event(
        owner="Beth",
        calendar_id="id",
        summary="Gym session",
        description="Leg day",
        start_time=datetime(2026, 4, 28, 9, 7, 30, tzinfo=timezone.utc),
    )
    notification = EventNotification(event=event, type=NotificationType.ALARM, offset=0, source=NotificationSource.ALARM_DESCRIPTION_TAG)
    notification.play_datetime = datetime(2026, 4, 28, 9, 5, tzinfo=timezone.utc)

    result = api_module.format_notification_for_api(notification)

    assert result.event.summary == "Gym session"
    assert result.type == "alarm"
    assert result.due_datetime == notification.notification_time
    assert result.play_datetime == datetime(2026, 4, 28, 9, 5, tzinfo=timezone.utc)


def test_format_notification_for_api_shows_the_leave_for_event_summary():
    target_event = Event(
        owner="Beth",
        calendar_id="id",
        summary="Dentist",
        description="#depart10",
        start_time=datetime(2026, 4, 28, 9, 0, tzinfo=timezone.utc),
    )
    scheduler = NotificationPlaytimeScheduler(timezone.utc, EventNotificationSchedule(), [], 5)
    leave_event = EventNotifications(target_event, scheduler).leave_for_event(datetime(2026, 4, 28, 8, 40, tzinfo=timezone.utc))
    notification = EventNotification(event=leave_event, type=NotificationType.ANNOUNCE, offset=0, source=NotificationSource.DEPART_DESCRIPTION_TAG)
    notification.play_datetime = datetime(2026, 4, 28, 8, 40, tzinfo=timezone.utc)

    result = api_module.format_notification_for_api(notification)

    assert result.event.summary == "Leave for Dentist"


def test_notifications_endpoint_returns_json_when_accept_header_requests_it(monkeypatch):
    event = Event(
        owner="Beth",
        calendar_id="id",
        summary="Gym session",
        description="Leg day",
        start_time=datetime(2026, 4, 28, 9, 7, 30, tzinfo=timezone.utc),
    )
    notification = EventNotification(event=event, type=NotificationType.ALARM, offset=0, source=NotificationSource.ALARM_DESCRIPTION_TAG)
    notification.play_datetime = datetime(2026, 4, 28, 9, 5, tzinfo=timezone.utc)
    monkeypatch.setattr(api_module, "get_all_event_notifications", lambda: [notification])
    monkeypatch.setattr(api_module, "scheduled_announcement_notifications", lambda: [])

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
                type=ScheduledAnnouncementType.MORNING_ANNOUNCEMENTS,
                due_datetime=datetime(2026, 4, 28, 7, 17, 0, tzinfo=timezone.utc),
            ),
            api_module.ScheduledAnnouncementNotification(
                summary="School announcements",
                type=ScheduledAnnouncementType.SCHOOL_ANNOUNCEMENTS,
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
                "play_datetime": "2026-04-28T07:17:00Z",
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


def test_morning_announcements_endpoint_passes_base_time(monkeypatch):
    calls = []
    monkeypatch.setattr(api_module, "play_morning_announcements", lambda base_time=None: calls.append(base_time))
    client = _client()
    monkeypatch.setattr(api_module.threading, "Thread", lambda target, args=(), daemon=False: SimpleNamespace(start=lambda: target(*args)))

    response = client.post("/alarm/morning-announcements", json={"base_time": "2026-04-28T07:15:00+00:00"})

    assert response.status_code == 202
    assert calls == [datetime(2026, 4, 28, 7, 15, tzinfo=timezone.utc)]


def test_school_announcements_endpoint_passes_base_time(monkeypatch):
    calls = []
    monkeypatch.setattr(api_module, "play_school_announcements", lambda base_time=None: calls.append(base_time))
    client = _client()
    monkeypatch.setattr(api_module.threading, "Thread", lambda target, args=(), daemon=False: SimpleNamespace(start=lambda: target(*args)))

    response = client.post("/alarm/school-announcements", json={"base_time": "2026-04-28T08:30:00+00:00"})

    assert response.status_code == 202
    assert calls == [datetime(2026, 4, 28, 8, 30, tzinfo=timezone.utc)]


def test_morning_announcements_endpoint_defaults_base_time_when_no_body_sent(monkeypatch):
    calls = []
    monkeypatch.setattr(api_module, "play_morning_announcements", lambda base_time=None: calls.append(base_time))
    client = _client()
    monkeypatch.setattr(api_module.threading, "Thread", lambda target, args=(), daemon=False: SimpleNamespace(start=lambda: target(*args)))

    response = client.post("/alarm/morning-announcements")

    assert response.status_code == 202
    assert calls == [None]


def test_snooze_endpoint_stops_the_alarm_with_snooze_flag_set(monkeypatch):
    calls = []
    monkeypatch.setattr(api_module.AlarmHandler, "stop_alarm", lambda self, snooze=False: calls.append(snooze) or "Stopping alarm...")

    response = _client().post("/alarm/snooze")

    assert response.status_code == 202
    assert response.text == "Stopping alarm..."
    assert calls == [True]


def test_recompute_departure_times_endpoint_recomputes_synchronously(monkeypatch):
    calls = []
    monkeypatch.setattr(api_module, "EventNotificationSettings", lambda: SimpleNamespace(location_based_departure_times=SimpleNamespace(enabled=True)))
    monkeypatch.setattr(api_module, "update_calendar_travel_times", lambda: calls.append("recalculated"))

    response = _client().post("/alarm/recompute-departure-times")

    assert response.status_code == 200
    assert response.text == "Departure times recalculated"
    assert calls == ["recalculated"]


def test_recompute_departure_times_endpoint_returns_conflict_when_the_calendar_data_is_locked(monkeypatch):
    monkeypatch.setattr(api_module, "EventNotificationSettings", lambda: SimpleNamespace(location_based_departure_times=SimpleNamespace(enabled=True)))
    monkeypatch.setattr(api_module, "update_calendar_travel_times", lambda: pytest.fail("must not recompute while locked"))

    with calendar_data_lock():
        response = _client().post("/alarm/recompute-departure-times")

    assert response.status_code == 409
    assert response.text == "Calendar data is already being updated"


def test_recompute_departure_times_endpoint_returns_conflict_when_departure_notifications_are_disabled(monkeypatch):
    monkeypatch.setattr(api_module, "EventNotificationSettings", lambda: SimpleNamespace(location_based_departure_times=SimpleNamespace(enabled=False)))
    monkeypatch.setattr(api_module, "update_calendar_travel_times", lambda: pytest.fail("must not recompute when disabled"))

    response = _client().post("/alarm/recompute-departure-times")

    assert response.status_code == 409
    assert response.text == "Location based departure notifications are disabled"


def test_refresh_calendar_data_endpoint_refreshes_synchronously(monkeypatch):
    calls = []
    monkeypatch.setattr(api_module, "refresh_calendar_data", lambda: calls.append("refreshed"))

    response = _client().post("/alarm/refresh-calendar-data")

    assert response.status_code == 200
    assert response.text == "Calendar data refreshed"
    assert calls == ["refreshed"]


def test_refresh_calendar_data_endpoint_returns_conflict_when_a_refresh_is_already_in_progress(monkeypatch):
    started = threading.Event()
    release = threading.Event()
    calls = []

    def slow_refresh():
        calls.append("refreshed")
        started.set()
        release.wait(timeout=5)

    monkeypatch.setattr(api_module, "refresh_calendar_data", slow_refresh)
    client = _client()
    first = threading.Thread(target=lambda: client.post("/alarm/refresh-calendar-data"))
    first.start()
    assert started.wait(timeout=5)

    try:
        response = client.post("/alarm/refresh-calendar-data")
    finally:
        release.set()
        first.join(timeout=5)

    assert response.status_code == 409
    assert response.text == "Calendar data is already being updated"
    assert calls == ["refreshed"]


def test_refresh_calendar_data_endpoint_returns_conflict_when_another_process_holds_the_calendar_data_lock(monkeypatch):
    monkeypatch.setattr(api_module, "refresh_calendar_data", lambda: pytest.fail("must not refresh while locked"))

    with calendar_data_lock():
        response = _client().post("/alarm/refresh-calendar-data")

    assert response.status_code == 409
    assert response.text == "Calendar data is already being updated"


def test_refresh_calendar_data_endpoint_releases_the_lock_when_the_refresh_fails(monkeypatch):
    def failing_refresh():
        raise RuntimeError("boom")

    monkeypatch.setattr(api_module, "refresh_calendar_data", failing_refresh)
    client = TestClient(_client().app, raise_server_exceptions=False)

    assert client.post("/alarm/refresh-calendar-data").status_code == 500
    monkeypatch.setattr(api_module, "refresh_calendar_data", lambda: None)
    assert client.post("/alarm/refresh-calendar-data").status_code == 200


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


def test_notifications_page_includes_event_json_and_play_datetime_for_the_test_button(monkeypatch):
    event = Event(
        owner="Beth",
        calendar_id="id",
        summary="Gym session",
        description="#alarm",
        start_time=datetime(2026, 4, 28, 9, 0, tzinfo=timezone.utc),
    )
    notification = EventNotification(event=event, type=NotificationType.ALARM, offset=0, source=NotificationSource.ALARM_DESCRIPTION_TAG)
    notification.play_datetime = datetime(2026, 4, 28, 8, 55, tzinfo=timezone.utc)
    monkeypatch.setattr(api_module, "get_all_event_notifications", lambda: [notification])

    response = _client().get("/alarm/notifications")

    assert response.status_code == 200
    assert 'data-event="' in response.text
    assert "test-notification" in response.text
    assert f'data-play-datetime="{notification.play_datetime.isoformat()}"' in response.text
    assert f'data-notification-time="{notification.notification_time.isoformat()}"' in response.text
    assert 'data-notification-type="ALARM"' in response.text


def test_test_notification_endpoint_starts_the_notification_test_and_returns_immediately(monkeypatch):
    calls = []
    monkeypatch.setattr(
        api_module.AlarmHandler,
        "test_notification",
        lambda self, *args: calls.append(args) or "Testing notification...",
    )

    event = {"owner": "Beth", "calendar_id": "id", "summary": "Gym session", "description": "#alarm"}
    play_datetime = datetime(2026, 4, 28, 8, 55, tzinfo=timezone.utc)
    notification_time = datetime(2026, 4, 28, 9, 0, tzinfo=timezone.utc)

    response = _client().post(
        "/alarm/test-notification",
        json={"event": event, "play_datetime": play_datetime.isoformat(), "notification_time": notification_time.isoformat(), "notification_type": "ALARM"},
    )

    assert response.status_code == 202
    assert response.text == "Testing notification..."
    assert calls == [(event, play_datetime, notification_time, "ALARM")]


def test_alarm_handler_test_notification_runs_test_notification_on_a_background_thread(monkeypatch):
    calls = []
    started = threading.Event()

    def fake_test_notification(*args):
        calls.append(args)
        started.set()

    monkeypatch.setattr(api_module, "test_notification", fake_test_notification)

    handler = api_module.AlarmHandler()
    event = {"summary": "Gym session"}
    play_datetime = datetime(2026, 4, 28, 8, 55, tzinfo=timezone.utc)
    notification_time = datetime(2026, 4, 28, 9, 0, tzinfo=timezone.utc)

    message = handler.test_notification(event, play_datetime, notification_time, "ALARM")

    assert message == "Testing notification..."
    assert started.wait(timeout=1)
    assert calls == [(event, play_datetime, notification_time, "ALARM")]
