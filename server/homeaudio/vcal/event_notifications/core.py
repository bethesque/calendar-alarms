from dataclasses import dataclass
import logging
from pathlib import Path
from homeaudio.vcal.cal.google_calendar import CalendarDay
from homeaudio.vcal.event_notifications.events import EventNotification, NotificationType
from homeaudio.housie_talkie.models import SoundEffectSelector
from homeaudio.vcal.event_notifications.audio import AlarmAudio, AnnouncementAudio
from homeaudio.vcal.event_notifications.text import NotificationTextBuilder
from homeaudio.vcal.event_notifications import snooze
from homeaudio.vcal.event_notifications.snooze import LastPlayedState
from homeaudio.vcal.event_notifications.events import get_event_notifications
from homeaudio.audio.settings import EventNotificationSettings, DepartureNotificationSettings
from homeaudio.audio.scene import SceneProtocol
from homeaudio.vcal.playback import NotificationFile, NotificationFiles, play_notifications

# "It's time for an event to begin, however there was a problem creating the announcement. Please check the calendar."
# The full notification file with bell and post-announcement silence.
ERROR_MESSAGE_AUDIO = str(Path("audio_resources/notification_error_notification.wav").absolute())

logger = logging.getLogger(__name__)

# Only used for testing
# Builds and immediately plays whatever calendar-driven notifications (plus any due snoozes) are
# due at base_time. Used by the cron-invoked cal-alarm-check entry point (event_notifications/cli.py).
def check_for_and_play_notifications(base_time, window, calendar_days: list[CalendarDay], scene: SceneProtocol, event_notification_settings: EventNotificationSettings | None = None, departure_notification_settings: DepartureNotificationSettings | None = None) -> None:
    event_notification_settings = event_notification_settings or EventNotificationSettings()
    announcements_file, alarm_audio_file = check_for_event_notifications(base_time, window, calendar_days, event_notification_settings, departure_notification_settings)
    if announcements_file or alarm_audio_file:
        play_notifications(
            NotificationFiles(event_alarms_file=alarm_audio_file, event_announcements_file=announcements_file),
            scene
        )

# Gathers what's due at base_time (calendar-driven notifications plus any due snoozes) and builds
# their announcement/alarm audio files, without playing them. Used by the daemon's early wake-up
# (homeaudio/vcal/daemon.py) so it can build audio ahead of a scheduled tick and play right on time;
# check_for_notifications above uses it too, just followed immediately by playing.
def check_for_event_notifications(base_time, window, calendar_days: list[CalendarDay], event_notification_settings: EventNotificationSettings | None = None, departure_notification_settings: DepartureNotificationSettings | None = None) -> tuple[NotificationFile | None, NotificationFile | None]:
    event_notification_settings = event_notification_settings or EventNotificationSettings()
    event_notifications = get_event_notifications(base_time, window, calendar_days, event_notification_settings, departure_notification_settings)
    event_notifications = event_notifications + snooze.due_snoozed_event_notifications(base_time)
    if not event_notifications:
        return (None, None)

    try:
        return _build_notification_files(event_notifications, base_time, event_notification_settings)
    except Exception:
        logger.exception("Error generating notification audio. Returning pre-generated notification file.")
        return (NotificationFile(path=ERROR_MESSAGE_AUDIO), None)

def _build_notification_files(event_notifications: list[EventNotification], base_time, event_notification_settings: EventNotificationSettings | None = None) -> tuple[NotificationFile | None, NotificationFile | None]:
    event_notification_settings = event_notification_settings or EventNotificationSettings()
    LastPlayedState().save(event_notifications, base_time)

    # Separate alarm and announcement notifications
    announcement_event_notifications = [event for event in event_notifications if event.type == NotificationType.ANNOUNCE]
    alarm_event_notifications = [event for event in event_notifications if event.type == NotificationType.ALARM]

    announcement_texts = NotificationTextBuilder(announcement_event_notifications, base_time).build()
    alarm_texts = NotificationTextBuilder(alarm_event_notifications, base_time).build()

    announcements_file = (
        NotificationFile(path=AnnouncementAudio(announcement_texts, base_time, SoundEffectSelector(event_notification_settings.announcements.sound_effect_probability)).build_announcement_file())
        if announcement_event_notifications else None
    )
    alarm_audio_file = (
        NotificationFile(path=AlarmAudio(alarm_texts, event_notification_settings.alarms, base_time).build_alarm_file())
        if alarm_event_notifications else None
    )

    return announcements_file, alarm_audio_file
