"""Long-running alternative to the cron/systemd-timer-triggered check_for_alarms.sh.

"""

import logging
import signal
import threading
from datetime import date, datetime, timedelta

from homeaudio.audio.log_config import setup_logging_for_alarms
from homeaudio.audio.scene import scene_for_env
from homeaudio.audio.settings import EventNotificationSchedule, EventNotificationSettings, MainSettings, TimeRange
from homeaudio.env import LOG_LEVEL
from homeaudio.vcal.cal.google_calendar import CalendarSource
from homeaudio.vcal.notifications.core import DATA_FILE, prepare_notification_files
from homeaudio.vcal.notifications.core import play_notifications as _play_notifications

setup_logging_for_alarms(str(LOG_LEVEL))

logger = logging.getLogger(__name__)

CHECK_WINDOW_MINUTES = 1

# How many seconds before each check tick the daemon wakes up to build notification audio,
# so playback can start exactly on the tick instead of after however long that build takes.
EARLY_WAKE_SECONDS = 15


def _time_range_for_day(schedule: EventNotificationSchedule, day: date) -> TimeRange:
    return schedule.weekdays if day.weekday() < 5 else schedule.weekends  # Monday=0 ... Sunday=6


def _within_operating_hours(dt: datetime, schedule: EventNotificationSchedule) -> bool:
    time_range = _time_range_for_day(schedule, dt.date())
    return time_range.start <= dt.time() < time_range.end


def next_boundary(now: datetime, schedule: EventNotificationSchedule | None = None) -> datetime:
    """The next CHECK_WINDOW_MINUTES-aligned time at or after `now`, skipping forward
    over hours outside EventNotificationSettings.schedule's weekdays/weekends window.

    `schedule` is read fresh from EventNotificationSettings() by default (rather than
    as a mutable default argument) so a change saved through the admin UI takes effect
    on the daemon's very next wake-up, not just at process start.
    """
    schedule = schedule or EventNotificationSettings().schedule

    minute = (now.minute // CHECK_WINDOW_MINUTES + 1) * CHECK_WINDOW_MINUTES
    candidate = now.replace(minute=0, second=0, microsecond=0) + timedelta(minutes=minute)

    while not _within_operating_hours(candidate, schedule):
        time_range = _time_range_for_day(schedule, candidate.date())
        if candidate.time() >= time_range.end:
            next_day = candidate.date() + timedelta(days=1)
            next_start = _time_range_for_day(schedule, next_day).start
            candidate = datetime.combine(next_day, next_start, tzinfo=candidate.tzinfo)
        else:
            candidate = datetime.combine(candidate.date(), time_range.start, tzinfo=candidate.tzinfo)

    return candidate


NotificationFiles = tuple[str | None, str | None]


def check_for_notifications(base_time: datetime) -> NotificationFiles | None:
    """Gathers what's due at `base_time` and builds its audio, without playing it - the
    "early wake-up" half of a tick. Returns None if there's nothing to play or the tick
    should be skipped (settings disabled, or an error while preparing)."""
    if not MainSettings().enabled:
        logger.info("Calendar Alarms are disabled in main settings; skipping this tick")
        return None

    if not EventNotificationSettings().enabled:
        logger.info("Event notifications are disabled in settings; skipping this tick")
        return None

    try:
        logger.info("Checking for alarms at %s", base_time)
        calendar_data = CalendarSource(cache_file_path=DATA_FILE).load_data_from_file()
        announcements_file, alarm_audio_file = prepare_notification_files(base_time, CHECK_WINDOW_MINUTES, calendar_data)
        return (announcements_file, alarm_audio_file) if (announcements_file or alarm_audio_file) else None
    except Exception:
        # A single bad tick must never kill the loop - log and try again next boundary.
        logger.exception("Error checking for alarms at %s", base_time)
        return None


def play_notification_files(notification_files: NotificationFiles) -> None:
    """Plays audio already built by check_for_notifications - the "on time" half of a tick."""
    announcements_file, alarm_audio_file = notification_files
    try:
        _play_notifications(announcements_file, alarm_audio_file, scene_for_env())
    except Exception:
        # A single bad tick must never kill the loop - log and try again next boundary.
        logger.exception("Error playing prepared notifications")


def check_for_and_play_notifications(base_time: datetime) -> None:
    """Prepares and immediately plays a tick's notifications, with no early wake-up - used for
    the daemon's startup catch-up, where there's no upcoming boundary to build ahead of."""
    notification_files = check_for_notifications(base_time)
    if notification_files is not None:
        play_notification_files(notification_files)


class AlarmCheckDaemon:
    def __init__(self):
        self._stop_event = threading.Event()

    def request_stop(self, *_args) -> None:
        logger.info("Shutdown requested; exiting after the current sleep")
        self._stop_event.set()

    def _interruptible_wait_until(self, target: datetime) -> bool:
        """Sleeps (interruptibly) until `target`. Returns True if a stop was requested during
        or before the sleep, so the caller should exit."""
        remaining = (target - datetime.now().astimezone()).total_seconds()
        if remaining > 0 and self._stop_event.wait(timeout=remaining):
            return True
        return self._stop_event.is_set()

    def run(self) -> None:
        signal.signal(signal.SIGTERM, self.request_stop)
        signal.signal(signal.SIGINT, self.request_stop)

        logger.info("Alarm check daemon starting")
        check_for_and_play_notifications(datetime.now().astimezone())  # startup catch-up, don't wait for the first boundary

        while not self._stop_event.is_set():
            target = next_boundary(datetime.now().astimezone())
            prepare_at = target - timedelta(seconds=EARLY_WAKE_SECONDS)

            if self._interruptible_wait_until(prepare_at):
                break

            notification_files = check_for_notifications(target)

            if notification_files is not None:
                if self._interruptible_wait_until(target):
                    break
                play_notification_files(notification_files)

        logger.info("Alarm check daemon stopped")


def run_daemon() -> None:
    AlarmCheckDaemon().run()
