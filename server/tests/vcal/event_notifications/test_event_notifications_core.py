from datetime import datetime
from pathlib import Path

from homeaudio.audio.settings import EventNotificationSettings
from homeaudio.vcal.cal.google_calendar import CalendarSource, Event, EventNotification, NotificationType
from homeaudio.vcal.event_notifications.core import ERROR_MESSAGE_AUDIO, check_for_event_notifications


def test_error_message_audio_file_exists():
    # check_for_event_notifications falls back to this pre-generated file when
    # notification audio generation raises, so it must exist on disk.
    assert Path(ERROR_MESSAGE_AUDIO).is_file()


def test_check_for_event_notifications_returns_error_message_audio_on_exception(monkeypatch):
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

    monkeypatch.setattr("homeaudio.vcal.event_notifications.core._build_notification_files", raise_error)

    result = check_for_event_notifications(
        base_time,
        5,
        calendar_data,
        EventNotificationSettings(notification_rules=[]),
    )

    assert result == (ERROR_MESSAGE_AUDIO, None)
