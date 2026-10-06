from datetime import datetime, time, timedelta
from zoneinfo import ZoneInfo

from homeaudio.audio.settings import EventNotificationSchedule, EventNotificationSettings, TimeRange
from homeaudio.vcal.cal.google_calendar import Event
from homeaudio.vcal.event_notifications.events import EventNotification, NotificationType
import homeaudio.vcal.core as core_module
from homeaudio.vcal.core import snooze_alarm
from homeaudio.vcal.event_notifications.snooze import LastPlayedState, SnoozeState

TIMEZONE = ZoneInfo("Australia/Melbourne")

SCHEDULE = EventNotificationSchedule(
    weekdays=TimeRange(start=time(7, 0), end=time(21, 0)),
    weekends=TimeRange(start=time(8, 0), end=time(21, 0)),
)


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
    monkeypatch.setattr(core_module, "play_file", lambda file: play_file_calls.append(file))

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
    assert SnoozeState()._load_raw()["clear_at"] == (base_time + timedelta(minutes=20)).isoformat()
    due = SnoozeState().due_event_notifications(replay_at)
    assert len(due) == 1
    assert due[0].event.summary == "Gym session"

    assert hook_calls == [1]


def _stub_test_notification_playback(monkeypatch):
    calls = {}
    monkeypatch.setattr(core_module, "gtts_tld", lambda: "com")
    monkeypatch.setattr(
        core_module,
        "build_event_notification_files",
        lambda notifications, base_time, tld, settings: calls.update(notifications=notifications, base_time=base_time) or ("announce.wav", "alarm.wav"),
    )
    monkeypatch.setattr(core_module, "play_notifications", lambda files, scene: calls.update(files=files, scene=scene))
    monkeypatch.setattr(core_module, "scene_for_env", lambda: "the-scene")
    return calls


def _gym_event_dict(start_time: datetime, description: str) -> dict:
    return {
        "owner": "Beth",
        "calendar_id": "id",
        "summary": "Gym session",
        "description": description,
        "start_time": start_time.isoformat(),
        "end_time": None,
        "recurring": False,
        "owner_count": 0,
        "location": None,
    }


def test_test_notification_plays_only_the_requested_notification_at_its_play_datetime(monkeypatch):
    calls = _stub_test_notification_playback(monkeypatch)
    monkeypatch.setattr(core_module, "EventNotificationSettings", lambda: EventNotificationSettings(schedule=SCHEDULE))
    start_time = datetime(2026, 4, 28, 22, 0, tzinfo=TIMEZONE)
    play_datetime = datetime(2026, 4, 28, 20, 55, tzinfo=TIMEZONE)

    core_module.test_notification(_gym_event_dict(start_time, "#alarm #announce10"), play_datetime, start_time, "ALARM")

    assert [(n.type, n.notification_time) for n in calls["notifications"]] == [(NotificationType.ALARM, start_time)]
    assert calls["base_time"] == play_datetime
    assert calls["files"].event_alarms_file == "alarm.wav"
    assert calls["files"].event_announcements_file == "announce.wav"
    assert calls["scene"] == "the-scene"


def test_test_notification_plays_nothing_when_the_requested_notification_is_not_found(monkeypatch):
    calls = _stub_test_notification_playback(monkeypatch)
    monkeypatch.setattr(core_module, "EventNotificationSettings", lambda: EventNotificationSettings(schedule=SCHEDULE))
    start_time = datetime(2026, 4, 28, 9, 0, tzinfo=TIMEZONE)

    core_module.test_notification(_gym_event_dict(start_time, "#alarm"), start_time, start_time, "ANNOUNCE")

    assert calls == {}

def test_prepare_notification_files_passes_a_scheduler_to_event_notifications_and_the_check_interval_to_announcements(monkeypatch):
    calls = {}
    monkeypatch.setattr(core_module, "gtts_tld", lambda: "com")
    monkeypatch.setattr(
        core_module,
        "check_for_event_notifications",
        lambda base_time, scheduler, *args: calls.setdefault("event", scheduler) and (None, None),
    )
    monkeypatch.setattr(core_module, "check_for_morning_announcements", lambda base_time, window, *args: calls.setdefault("morning", window) and None)
    monkeypatch.setattr(core_module, "check_for_school_announcements", lambda base_time, window, *args: calls.setdefault("school", window) and None)

    core_module.prepare_notification_files(datetime(2026, 4, 28, 7, 0, tzinfo=TIMEZONE), [], 5, EventNotificationSettings(schedule=SCHEDULE))

    assert calls.pop("event").window == 5
    assert calls == {"morning": 5, "school": 5}
