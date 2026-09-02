from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

from homeaudio.audio.settings import NotificationRule
from homeaudio.vcal.cal.google_calendar import Event, EventNotification, NotificationType
from homeaudio.vcal.notifications.snooze import LastPlayedState, SnoozeState, _deserialize, _serialize

TIMEZONE = ZoneInfo("Australia/Melbourne")


def _event_notification(summary="Gym session", type=NotificationType.ALARM, offset=0, notification_rule=None):
    event = Event(
        owner="Beth",
        calendar_id="id",
        summary=summary,
        description="#alarm",
        start_time=datetime(2026, 4, 28, 7, 0, tzinfo=TIMEZONE),
        location="Croydon",
    )
    return EventNotification(event=event, type=type, offset=offset, notification_rule=notification_rule)


def test_serialize_deserialize_round_trips_event_notification_without_rule():
    event_notification = _event_notification(type=NotificationType.ANNOUNCE, offset=5)

    round_tripped = _deserialize(_serialize(event_notification))

    assert round_tripped.event == event_notification.event
    assert round_tripped.type == NotificationType.ANNOUNCE
    assert round_tripped.offset == 5
    assert round_tripped.notification_rule is None


def test_serialize_deserialize_round_trips_event_notification_with_rule():
    rule = NotificationRule(summary_pattern="Gym", offset_minutes=0, reminder="Remember to eat.")
    event_notification = _event_notification(notification_rule=rule)

    round_tripped = _deserialize(_serialize(event_notification))

    assert round_tripped.notification_rule.summary_pattern == "Gym"
    assert round_tripped.notification_rule.reminder == "Remember to eat."


def _fresh_state_files(monkeypatch, tmp_path):
    last_played_path = str(tmp_path / "last_played.json")
    snooze_path = str(tmp_path / "snooze.json")
    monkeypatch.setattr(LastPlayedState, "file_path", last_played_path)
    monkeypatch.setattr(SnoozeState, "file_path", snooze_path)


def test_last_played_state_save_load_clear(monkeypatch, tmp_path):
    _fresh_state_files(monkeypatch, tmp_path)

    state = LastPlayedState()
    assert state.load() == []
    assert state.load_base_time() is None
    assert state.fresh() is False

    event_notification = _event_notification()
    base_time = datetime(2026, 4, 28, 7, 30, tzinfo=TIMEZONE)
    state.save([event_notification], base_time)

    loaded = state.load()
    assert len(loaded) == 1
    assert loaded[0].event.summary == "Gym session"
    assert state.load_base_time() == base_time
    assert state.fresh() is True

    state.clear()
    assert state.load() == []
    assert state.load_base_time() is None
    assert state.fresh() is False


def test_snooze_state_due_event_notifications_only_returns_when_due(monkeypatch, tmp_path):
    _fresh_state_files(monkeypatch, tmp_path)

    now = datetime(2026, 4, 28, 7, 30, tzinfo=TIMEZONE)
    replay_at = now + timedelta(minutes=9)

    state = SnoozeState()
    state.save([_event_notification()], replay_at)

    assert state.next_replay_at() == replay_at
    assert state.due_event_notifications(now) == []  # not due yet, and not cleared
    assert state.next_replay_at() == replay_at  # still pending

    due = state.due_event_notifications(replay_at)
    assert len(due) == 1
    assert due[0].event.summary == "Gym session"

    # Cleared once returned.
    assert state.next_replay_at() is None
    assert state.due_event_notifications(replay_at) == []


def test_snooze_state_next_replay_at_is_none_when_nothing_pending(monkeypatch, tmp_path):
    _fresh_state_files(monkeypatch, tmp_path)

    assert SnoozeState().next_replay_at() is None
