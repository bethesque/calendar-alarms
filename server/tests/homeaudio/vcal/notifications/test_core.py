from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

from homeaudio.audio.settings import EventNotificationSettings, NotificationRule
from homeaudio.vcal.cal.google_calendar import CalendarSource, Event, EventNotification, NotificationType
import homeaudio.vcal.notifications.core as core_module
from homeaudio.vcal.notifications.core import get_event_notifications, snooze_alarm
from homeaudio.vcal.notifications.snooze import LastPlayedState, SnoozeState

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


def _event_notification():
    event = Event(
        owner="Beth",
        calendar_id="id",
        summary="Gym session",
        description="#alarm",
        start_time=datetime(2026, 4, 28, 9, 0, tzinfo=TIMEZONE),
    )
    return EventNotification(event=event, type=NotificationType.ALARM, offset=0)


def _stub_snooze_alarm_playback(monkeypatch):
    # Avoid hitting gTTS/ffmpeg/mpd to build and play real audio - only the
    # message/file being passed around is what these tests check.
    announcement_calls = []
    play_file_calls = []

    monkeypatch.setattr(
        core_module,
        "_build_one_off_announcement_file",
        lambda message: announcement_calls.append(message) or f"announcement_for::{message}",
    )
    monkeypatch.setattr(core_module, "_play_file", lambda file: play_file_calls.append(file))

    return announcement_calls, play_file_calls


def _stub_state_files(monkeypatch, tmp_path):
    monkeypatch.setattr(LastPlayedState, "file_path", str(tmp_path / "last_played.json"))
    monkeypatch.setattr(SnoozeState, "file_path", str(tmp_path / "snooze.json"))


def test_snooze_alarm_stops_playback_and_announces_nothing_to_snooze_when_nothing_last_played(monkeypatch, tmp_path):
    _stub_state_files(monkeypatch, tmp_path)
    announcement_calls, play_file_calls = _stub_snooze_alarm_playback(monkeypatch)

    stop_alarm_calls = []
    monkeypatch.setattr(core_module, "stop_alarm", lambda hook=None: stop_alarm_calls.append(hook))

    hook_calls = []
    snooze_alarm(after_alarm_hook=lambda: hook_calls.append(1))

    assert stop_alarm_calls == [None]
    assert announcement_calls == ["Nothing to snooze"]
    assert play_file_calls == ["announcement_for::Nothing to snooze"]
    assert SnoozeState().next_replay_at() is None
    assert hook_calls == []  # the hook is only run after a successful snooze


def test_snooze_alarm_announces_nothing_to_snooze_when_last_played_batch_is_empty(monkeypatch, tmp_path):
    _stub_state_files(monkeypatch, tmp_path)
    announcement_calls, play_file_calls = _stub_snooze_alarm_playback(monkeypatch)
    monkeypatch.setattr(core_module, "stop_alarm", lambda hook=None: None)

    base_time = datetime(2026, 4, 28, 9, 0, tzinfo=TIMEZONE)
    LastPlayedState().save([], base_time)

    hook_calls = []
    snooze_alarm(after_alarm_hook=lambda: hook_calls.append(1))

    assert announcement_calls == ["Nothing to snooze"]
    assert play_file_calls == ["announcement_for::Nothing to snooze"]
    assert SnoozeState().next_replay_at() is None
    assert hook_calls == []


def test_snooze_alarm_saves_snooze_state_and_confirms_via_tts(monkeypatch, tmp_path):
    _stub_state_files(monkeypatch, tmp_path)
    announcement_calls, play_file_calls = _stub_snooze_alarm_playback(monkeypatch)

    stop_alarm_calls = []
    monkeypatch.setattr(core_module, "stop_alarm", lambda hook=None: stop_alarm_calls.append(hook))
    monkeypatch.setattr(
        core_module,
        "EventNotificationSettings",
        lambda: type("_S", (), {"snooze_minutes": 10})(),
    )

    base_time = datetime(2026, 4, 28, 9, 0, tzinfo=TIMEZONE)
    event_notification = _event_notification()
    LastPlayedState().save([event_notification], base_time)

    hook_calls = []
    snooze_alarm(after_alarm_hook=lambda: hook_calls.append(1))

    assert stop_alarm_calls == [None]
    assert len(announcement_calls) == 1
    assert "Snoozing for" in announcement_calls[0] and "minutes" in announcement_calls[0]
    assert play_file_calls == [f"announcement_for::{announcement_calls[0]}"]

    replay_at = base_time + timedelta(minutes=10)
    assert SnoozeState().next_replay_at() == replay_at
    due = SnoozeState().due_event_notifications(replay_at)
    assert len(due) == 1
    assert due[0].event.summary == "Gym session"

    assert hook_calls == [1]
