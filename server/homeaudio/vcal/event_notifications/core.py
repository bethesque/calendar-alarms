from dataclasses import dataclass
from datetime import datetime
import logging
from pathlib import Path
from homeaudio.vcal.cal.google_calendar import CalendarDay, CalendarDayList, CalendarSource
from homeaudio.vcal.event_notifications.events import EventNotification, EventNotifications, NotificationPlaytimeScheduler, NotificationType
from homeaudio.housie_talkie.models import SoundEffectSelector
from homeaudio.vcal.event_notifications.audio import AlarmAudio, AnnouncementAudio
from homeaudio.vcal.event_notifications.text import NotificationTextBuilder
from homeaudio.vcal.event_notifications.text_to_voice import gtts_tld
from homeaudio.vcal.event_notifications import snooze
from homeaudio.vcal.event_notifications.snooze import LastPlayedState, SnoozeState
from homeaudio.vcal.event_notifications.events import get_event_notifications
from homeaudio.audio.settings import EventNotificationSettings
from homeaudio.audio.scene import SceneProtocol
from homeaudio.env import NOTIFICATIONS_CHECK_INTERVAL_MINUTES
from homeaudio.vcal.playback import NotificationFile, NotificationFiles, play_notifications

# "It's time for an event to begin, however there was a problem creating the announcement. Please check the calendar."
# The full notification file with bell and post-announcement silence.
ERROR_MESSAGE_AUDIO = str(Path("audio_resources/notification_error_notification.wav").absolute())

logger = logging.getLogger(__name__)

# Only used for testing
# Builds and immediately plays whatever calendar-driven notifications (plus any due snoozes) are
# due at base_time. Used by the cron-invoked cal-alarm-check entry point (event_notifications/cli.py).
def check_for_and_play_notifications(base_time, scheduler: NotificationPlaytimeScheduler, calendar_days: CalendarDayList, scene: SceneProtocol, event_notification_settings: EventNotificationSettings | None = None) -> None:
    event_notification_settings = event_notification_settings or EventNotificationSettings()
    announcements_file, alarm_audio_file = check_for_event_notifications(base_time, scheduler, calendar_days, gtts_tld(), event_notification_settings)
    if announcements_file or alarm_audio_file:
        play_notifications(
            NotificationFiles(event_alarms_file=alarm_audio_file, event_announcements_file=announcements_file),
            scene
        )

# Gathers what's due at base_time (calendar-driven notifications plus any due snoozes) and builds
# their announcement/alarm audio files, without playing them. Used by the daemon's early wake-up
# (homeaudio/vcal/daemon.py) so it can build audio ahead of a scheduled tick and play right on time;
# check_for_notifications above uses it too, just followed immediately by playing.
def find_due_event_notifications(base_time, scheduler: NotificationPlaytimeScheduler, calendar_days: CalendarDayList, event_notification_settings: EventNotificationSettings | None = None) -> list[EventNotification]:
    event_notification_settings = event_notification_settings or EventNotificationSettings()
    event_notifications = get_event_notifications(base_time, scheduler, calendar_days, event_notification_settings)
    event_notifications = event_notifications + snooze.due_snoozed_event_notifications(base_time, scheduler)
    return event_notifications

# Gathers what's due at base_time (calendar-driven notifications plus any due snoozes) and builds
# their announcement/alarm audio files, without playing them. Used by the daemon's early wake-up
# (homeaudio/vcal/daemon.py) so it can build audio ahead of a scheduled tick and play right on time;
# check_for_notifications above uses it too, just followed immediately by playing.
def check_for_event_notifications(base_time, scheduler: NotificationPlaytimeScheduler, calendar_days: CalendarDayList, tld: str, event_notification_settings: EventNotificationSettings | None = None) -> tuple[NotificationFile | None, NotificationFile | None]:
    event_notifications = find_due_event_notifications(base_time, scheduler, calendar_days, event_notification_settings)
    if not event_notifications:
        return (None, None)

    return build_event_notification_files(event_notifications, base_time, tld, event_notification_settings)


def build_event_notification_files(event_notifications: list[EventNotification], base_time, tld: str, event_notification_settings: EventNotificationSettings | None = None) -> tuple[NotificationFile | None, NotificationFile | None]:
    try:

        event_notification_settings = event_notification_settings or EventNotificationSettings()
        LastPlayedState().save(event_notifications, base_time)

        # If all notifications have the same target, keep it, otherwise, play all notifications for everyone
        # It's too complicated to work out the logic otherwise
        unique_targets = { n.targets for n in event_notifications }
        targets = list(unique_targets)[0] if len(unique_targets) == 1 else None

        # Separate alarm and announcement notifications
        announcement_event_notifications = [event for event in event_notifications if event.type == NotificationType.ANNOUNCE]
        alarm_event_notifications = [event for event in event_notifications if event.type == NotificationType.ALARM]

        announcement_texts = NotificationTextBuilder(announcement_event_notifications, base_time, event_notification_settings.peoples_names).build()
        alarm_texts = NotificationTextBuilder(alarm_event_notifications, base_time, event_notification_settings.peoples_names).build()

        announcements_file = None
        alarm_audio_file = None

        if announcement_event_notifications:
            logger.info(f"Building audio for announcements: {announcement_texts}")
            announcements_file = NotificationFile(
                path=AnnouncementAudio(announcement_texts, base_time, tld, SoundEffectSelector(event_notification_settings.announcements.sound_effect_probability)).build_announcement_file(),
                targets=targets
            )

        if alarm_event_notifications:
            logger.info(f"Building audio for alarms: {alarm_texts}")
            alarm_audio_file = NotificationFile(
                path=AlarmAudio(alarm_texts, tld, event_notification_settings.alarms, base_time).build_alarm_file(),
                targets=targets
            )

        return announcements_file, alarm_audio_file
    except Exception:
        logger.exception("Error generating notification audio. Returning pre-generated notification file.")
        return (NotificationFile(path=ERROR_MESSAGE_AUDIO, targets=None), None)

def get_all_event_notifications(event_notification_settings: EventNotificationSettings | None = None, calendar_source: CalendarSource = CalendarSource()):
    event_notification_settings = event_notification_settings or EventNotificationSettings()
    calendar_days = calendar_source.load_data_from_file()

    scheduler = NotificationPlaytimeScheduler(datetime.now().astimezone().tzinfo, event_notification_settings.schedule, calendar_days, NOTIFICATIONS_CHECK_INTERVAL_MINUTES)
    notifications = []
    for day in calendar_days:
        for event in day.timed_events:
            notifications.extend(EventNotifications(event, scheduler).notifications(event_notification_settings))

    notifications.extend(SnoozeState().pending_event_notifications(datetime.now().astimezone(), scheduler))

    return notifications
