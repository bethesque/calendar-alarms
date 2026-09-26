from datetime import datetime
from pathlib import Path

from homeaudio.audio.settings import EventNotificationSettings
from homeaudio.vcal.cal.google_calendar import CalendarSource, Event
from homeaudio.vcal.event_notifications.events import EventNotification, NotificationType
from homeaudio.vcal.event_notifications.core import ERROR_MESSAGE_AUDIO, build_event_notification_files, check_for_event_notifications
from homeaudio.vcal.event_notifications.snooze import LastPlayedState
from homeaudio.vcal.playback import NotificationFile


class _StubAnnouncementAudio:
    def __init__(self, *args, **kwargs):
        pass

    def build_announcement_file(self):
        return "fake_announcement.wav"


class _StubAlarmAudio:
    def __init__(self, *args, **kwargs):
        pass

    def build_alarm_file(self):
        return "fake_alarm.wav"


def _stub_audio_building(monkeypatch):
    # Avoid hitting gTTS/ffmpeg to build real audio - these tests are only
    # concerned with the targets logic in build_event_notification_files.
    monkeypatch.setattr("homeaudio.vcal.event_notifications.core.AnnouncementAudio", _StubAnnouncementAudio)
    monkeypatch.setattr("homeaudio.vcal.event_notifications.core.AlarmAudio", _StubAlarmAudio)


def _event_notification(monkeypatch, tmp_path, base_time, type=NotificationType.ANNOUNCE, targets=None):
    monkeypatch.setattr(LastPlayedState, "file_path", str(tmp_path / "last_played.json"))
    event = Event(
        owner="Beth",
        calendar_id="id",
        summary="Take out the bins",
        description="",
        start_time=base_time,
    )
    return EventNotification(event=event, type=type, offset=0, targets=targets)


def test_error_message_audio_file_exists():
    # check_for_event_notifications falls back to this pre-generated file when
    # notification audio generation raises, so it must exist on disk.
    assert Path(ERROR_MESSAGE_AUDIO).is_file()


def test_check_for_event_notifications_returns_error_message_audio_on_exception(monkeypatch, tmp_path):
    monkeypatch.setattr(LastPlayedState, "file_path", str(tmp_path / "last_played.json"))
    base_time = datetime.fromisoformat("2026-04-06T08:00:00+10:00")
    calendar_data = CalendarSource(cache_file_path="").load_data_from_any([])  # not used, since get_event_notifications is stubbed below

    # A due notification so there's something for check_for_event_notifications
    # to try (and fail) to build audio for.
    due_event = Event(
        owner="Beth",
        calendar_id="id",
        summary="Take out the bins",
        description="",
        start_time=base_time,
    )
    due_notification = EventNotification(event=due_event, type=NotificationType.ANNOUNCE, offset=0)
    monkeypatch.setattr(
        "homeaudio.vcal.event_notifications.core.get_event_notifications",
        lambda base_time, window, calendar_days, event_notification_settings, departure_notification_settings=None: [due_notification],
    )

    def raise_error(*args, **kwargs):
        raise RuntimeError("boom")

    monkeypatch.setattr("homeaudio.vcal.event_notifications.core.AnnouncementAudio", raise_error)

    result = check_for_event_notifications(
        base_time,
        5,
        calendar_data,
        "com",
        EventNotificationSettings(notification_rules=[]),
    )

    assert result == (NotificationFile(path=ERROR_MESSAGE_AUDIO, targets=None), None)


def test_build_event_notification_files_uses_shared_target_when_all_notifications_agree(monkeypatch, tmp_path):
    _stub_audio_building(monkeypatch)
    base_time = datetime.fromisoformat("2026-04-06T08:00:00+10:00")
    targets = frozenset({"kitchen"})

    announcement_notification = _event_notification(monkeypatch, tmp_path, base_time, type=NotificationType.ANNOUNCE, targets=targets)
    alarm_notification = _event_notification(monkeypatch, tmp_path, base_time, type=NotificationType.ALARM, targets=targets)

    announcements_file, alarm_audio_file = build_event_notification_files(
        [announcement_notification, alarm_notification], base_time, "com", EventNotificationSettings()
    )

    assert announcements_file.targets == targets
    assert alarm_audio_file.targets == targets


def test_build_event_notification_files_returns_none_target_when_notifications_disagree(monkeypatch, tmp_path):
    _stub_audio_building(monkeypatch)
    base_time = datetime.fromisoformat("2026-04-06T08:00:00+10:00")

    kitchen_notification = _event_notification(monkeypatch, tmp_path, base_time, type=NotificationType.ANNOUNCE, targets=frozenset({"kitchen"}))
    bedroom_notification = _event_notification(monkeypatch, tmp_path, base_time, type=NotificationType.ALARM, targets=frozenset({"bedroom"}))

    announcements_file, alarm_audio_file = build_event_notification_files(
        [kitchen_notification, bedroom_notification], base_time, "com", EventNotificationSettings()
    )

    assert announcements_file.targets is None
    assert alarm_audio_file.targets is None


def test_build_event_notification_files_returns_none_target_when_one_notification_is_untargeted(monkeypatch, tmp_path):
    _stub_audio_building(monkeypatch)
    base_time = datetime.fromisoformat("2026-04-06T08:00:00+10:00")

    kitchen_notification = _event_notification(monkeypatch, tmp_path, base_time, type=NotificationType.ANNOUNCE, targets=frozenset({"kitchen"}))
    untargeted_notification = _event_notification(monkeypatch, tmp_path, base_time, type=NotificationType.ANNOUNCE, targets=None)

    announcements_file, _ = build_event_notification_files(
        [kitchen_notification, untargeted_notification], base_time, "com", EventNotificationSettings()
    )

    assert announcements_file.targets is None


def test_build_event_notification_files_returns_none_target_when_no_notification_has_targets(monkeypatch, tmp_path):
    _stub_audio_building(monkeypatch)
    base_time = datetime.fromisoformat("2026-04-06T08:00:00+10:00")

    first_notification = _event_notification(monkeypatch, tmp_path, base_time, type=NotificationType.ANNOUNCE, targets=None)
    second_notification = _event_notification(monkeypatch, tmp_path, base_time, type=NotificationType.ALARM, targets=None)

    announcements_file, alarm_audio_file = build_event_notification_files(
        [first_notification, second_notification], base_time, "com", EventNotificationSettings()
    )

    assert announcements_file.targets is None
    assert alarm_audio_file.targets is None
