"""
The main calendar alarms process that checks for and plays notifications and announcements.

"""

import logging
import signal
import threading
from datetime import datetime, timedelta

from homeaudio.audio.log_config import setup_logging_for_alarms
from homeaudio.audio.scene import scene_for_env
from homeaudio.audio.settings import EventNotificationSettings, MainSettings
from homeaudio.env import LOG_LEVEL, NOTIFICATIONS_CHECK_INTERVAL_MINUTES, NOTIFICATIONS_PREPARATION_LEAD_TIME_SECONDS
from homeaudio.vcal.cal.google_calendar import CalendarSource
from homeaudio.vcal.calendar_refresh import CalendarRefreshLoop
from homeaudio.vcal.core import prepare_notification_files, NotificationFiles
from homeaudio.vcal.core import play_notifications as _play_notifications

setup_logging_for_alarms(str(LOG_LEVEL))

logger = logging.getLogger(__name__)

# How often to check for and play notifications
CHECK_INTERVAL_MINUTES = NOTIFICATIONS_CHECK_INTERVAL_MINUTES

# How many seconds before each check tick the daemon wakes up to build notification audio,
# so playback can start exactly on the tick instead of after however long that build takes.
EARLY_WAKE_SECONDS = NOTIFICATIONS_PREPARATION_LEAD_TIME_SECONDS


def next_boundary(now: datetime) -> datetime:
    """The next CHECK_INTERVAL_MINUTES-aligned time after `now`."""
    minute = (now.minute // CHECK_INTERVAL_MINUTES + 1) * CHECK_INTERVAL_MINUTES
    return now.replace(minute=0, second=0, microsecond=0) + timedelta(minutes=minute)


def check_for_notifications(base_time: datetime) -> NotificationFiles | None:
    """Gathers what's due at `base_time` and builds its audio, without playing it - the
    "early wake-up" half of a tick. Returns None if there's nothing to play or the tick
    should be skipped (settings disabled, or an error while preparing)."""
    if not MainSettings().enabled:
        logger.info("Calendar Alarms are disabled in main settings; skipping this tick")
        return None

    event_notification_settings = EventNotificationSettings()
    if not event_notification_settings.enabled:
        logger.info("Event notifications are disabled in settings; skipping this tick")
        return None

    try:
        logger.info("Checking for notifications due at %s", base_time)
        calendar_source = CalendarSource()
        if calendar_source.file_exists():
            logger.debug(f"Loading calendar data from {calendar_source.cache_file_path}")
            calendar_days = calendar_source.load_data_from_file()
            return prepare_notification_files(base_time, calendar_days, CHECK_INTERVAL_MINUTES, event_notification_settings)
        else:
            logger.info(f"No calendar file found at {calendar_source.cache_file_path}, no notifications this tick")

    except Exception:
        # A single bad tick must never kill the loop - log and try again next boundary.
        logger.exception("Error checking for alarms at %s", base_time)
        return None


def play_notification_files(notification_files: NotificationFiles) -> None:
    """Plays audio already built by check_for_notifications - the "on time" half of a tick."""
    try:
        _play_notifications(notification_files, scene_for_env())
    except Exception:
        # A single bad tick must never kill the loop - log and try again next boundary.
        logger.exception("Error playing prepared notifications")


class NotificationCheckDaemon:
    def __init__(self):
        self._stop_event = threading.Event()

    def request_stop(self, *_args) -> None:
        logger.info("Shutdown requested; exiting after the current sleep")
        self._stop_event.set()

    def _interruptible_wait_until(self, target: datetime) -> bool:
        """Sleeps (interruptibly) until `target`. Returns True if a stop was requested during
        or before the sleep, so the caller should exit."""
        remaining = (target - datetime.now().astimezone()).total_seconds()
        logger.debug(f"Sleeping for {remaining:.2f} seconds until {target}")
        if remaining > 0 and self._stop_event.wait(timeout=remaining):
            return True
        return self._stop_event.is_set()

    def run(self) -> None:
        signal.signal(signal.SIGTERM, self.request_stop)
        signal.signal(signal.SIGINT, self.request_stop)

        refresh_thread = CalendarRefreshLoop(self._stop_event).start()

        logger.info(f"Started notification check daemon. Checking for notifications every {CHECK_INTERVAL_MINUTES} minutes, preparing sound files {EARLY_WAKE_SECONDS} seconds beforehand.")

        try:
            while not self._stop_event.is_set():
                play_at = next_boundary(datetime.now().astimezone())
                prepare_at = play_at - timedelta(seconds=EARLY_WAKE_SECONDS)

                if self._interruptible_wait_until(prepare_at):
                    break

                notification_files = check_for_notifications(play_at)

                if self._interruptible_wait_until(play_at):
                    break

                if notification_files is not None:
                    play_notification_files(notification_files)
        finally:
            # Ensures the refresh thread (which shares this event) is told to stop even when the
            # notification loop above exits via break rather than the top-of-loop stop check.
            self._stop_event.set()
            # Without this, run() can return - and the process exit - before the refresh thread
            # (a daemon thread) gets scheduled to run its own post-loop shutdown code, cutting it
            # off mid-flight.
            refresh_thread.join()

        logger.info("Stopped alarm check daemon")


def run_daemon() -> None:
    NotificationCheckDaemon().run()
