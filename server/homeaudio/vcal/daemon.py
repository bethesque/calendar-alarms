"""Long-running alternative to the cron/systemd-timer-triggered check_for_alarms.sh.

"""

import logging
import signal
import threading
from datetime import date, datetime, time, timedelta

from homeaudio.audio.log_config import setup_logging_for_alarms
from homeaudio.audio.scene import scene_for_env
from homeaudio.audio.settings import (
    EventNotificationSchedule,
    EventNotificationSettings,
    MainSettings,
    MorningAnnouncementsSchedule,
    MorningAnnouncementsSettings,
    SchoolAnnouncementsSchedule,
    SchoolAnnouncementsSettings,
    TimeRange,
)
from homeaudio.env import LOG_LEVEL
from homeaudio.vcal.cal.google_calendar import CalendarSource
from homeaudio.vcal.core import prepare_notification_files, NotificationFiles
from homeaudio.vcal.core import play_notifications as _play_notifications

setup_logging_for_alarms(str(LOG_LEVEL))

logger = logging.getLogger(__name__)

CHECK_WINDOW_MINUTES = 1

# How many seconds before each check tick the daemon wakes up to build notification audio,
# so playback can start exactly on the tick instead of after however long that build takes.
EARLY_WAKE_SECONDS = 15

# The longest next_boundary() will ever ask the daemon to sleep in one go, so a schedule
# change saved through the admin UI mid-sleep is noticed within the hour instead of only once
# a long, already-stale overnight wait finally ends.
MAX_SLEEP_SECONDS = 60 * 60


def _time_range_for_day(schedule: EventNotificationSchedule, day: date) -> TimeRange:
    return schedule.weekdays if day.weekday() < 5 else schedule.weekends  # Monday=0 ... Sunday=6


def _within_event_notification_operating_hours(dt: datetime, schedule: EventNotificationSchedule) -> bool:
    time_range = _time_range_for_day(schedule, dt.date())
    return time_range.start <= dt.time() < time_range.end


def _announcement_times_for_day(
    day: date,
    morning_schedule: MorningAnnouncementsSchedule,
    school_schedule: SchoolAnnouncementsSchedule,
) -> list[time]:
    """Times on `day` a morning/school announcement is due outside of - and so not otherwise
    covered by - EventNotificationSettings.schedule's operating hours."""
    is_weekday = day.weekday() < 5  # Monday=0 ... Sunday=6
    morning_time = morning_schedule.weekdays if is_weekday else morning_schedule.weekends
    school_time = school_schedule.weekdays if is_weekday else None  # school announcements never run on weekends
    return [scheduled_time for scheduled_time in (morning_time, school_time) if scheduled_time is not None]


def _is_scheduled_announcement(
    dt: datetime,
    morning_schedule: MorningAnnouncementsSchedule,
    school_schedule: SchoolAnnouncementsSchedule,
) -> bool:
    return dt.time() in _announcement_times_for_day(dt.date(), morning_schedule, school_schedule)


def _wake_times_for_day(
    day: date,
    schedule: EventNotificationSchedule,
    morning_schedule: MorningAnnouncementsSchedule,
    school_schedule: SchoolAnnouncementsSchedule,
) -> list[time]:
    """
    The announcement times and the start of the event notification time range.
    """
    return [
        _time_range_for_day(schedule, day).start,
        *_announcement_times_for_day(day, morning_schedule, school_schedule),
    ]


def next_boundary(
    now: datetime,
    schedule: EventNotificationSchedule | None = None,
    morning_schedule: MorningAnnouncementsSchedule | None = None,
    school_schedule: SchoolAnnouncementsSchedule | None = None,
) -> datetime:
    """The next CHECK_WINDOW_MINUTES-aligned time at or after `now`, skipping forward over hours
    outside EventNotificationSettings.schedule's weekdays/weekends window - except for any
    MorningAnnouncementsSettings/SchoolAnnouncementsSettings scheduled time that falls in one of
    those skipped hours, since those announcements are due regardless of that window.

    Each schedule is read fresh from its settings by default (rather than as a mutable default
    argument) so a change saved through the admin UI takes effect on the daemon's very next
    wake-up, not just at process start.

    The result is also capped to at most MAX_SLEEP_SECONDS after `now`, so a long gap outside
    operating hours (overnight, or a weekend) doesn't leave the daemon asleep on a boundary
    computed from settings that go on to change before it wakes - it re-derives the boundary
    from whatever the settings currently are at least that often.
    """
    schedule = schedule or EventNotificationSettings().schedule
    morning_schedule = morning_schedule or MorningAnnouncementsSettings().schedule
    school_schedule = school_schedule or SchoolAnnouncementsSettings().schedule

    minute = (now.minute // CHECK_WINDOW_MINUTES + 1) * CHECK_WINDOW_MINUTES
    # Wind back to the previous whole minute and add the CHECK_WINDOW_MINUTES to it
    candidate = now.replace(minute=0, second=0, microsecond=0) + timedelta(minutes=minute)

    while not _within_event_notification_operating_hours(candidate, schedule) and not _is_scheduled_announcement(
        candidate, morning_schedule, school_schedule
    ):
        # The next regular CHECK_WINDOW_MINUTES is outside the normal event notification operating hours.
        # Collect the future wake up times for today (the start of event notifications and the announcement times)
        wake_times_today = [
            wake_time
            for wake_time in _wake_times_for_day(candidate.date(), schedule, morning_schedule, school_schedule)
            if wake_time > candidate.time()
        ]
        # If there are future wake up times
        if wake_times_today:
            #... take the first one
            candidate = datetime.combine(candidate.date(), min(wake_times_today), tzinfo=candidate.tzinfo)
        else:
            # ... else get the next wake up time for tomorrow
            next_day = candidate.date() + timedelta(days=1)
            next_wake_times = _wake_times_for_day(next_day, schedule, morning_schedule, school_schedule)
            candidate = datetime.combine(next_day, min(next_wake_times), tzinfo=candidate.tzinfo)

    return min(candidate, now + timedelta(seconds=MAX_SLEEP_SECONDS))


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
        logger.info("Checking for notifications due at %s", base_time)
        calendar_source = CalendarSource()
        if calendar_source.file_exists():
            logger.info(f"Loading calendar data from {calendar_source.cache_file_path}")
            calendar_data = calendar_source.load_data_from_file()
            return prepare_notification_files(base_time, CHECK_WINDOW_MINUTES, calendar_data)
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
        logger.debug(f"Sleeping for {remaining:.2f} seconds until {target}")
        if remaining > 0 and self._stop_event.wait(timeout=remaining):
            return True
        return self._stop_event.is_set()

    def run(self) -> None:
        signal.signal(signal.SIGTERM, self.request_stop)
        signal.signal(signal.SIGINT, self.request_stop)

        logger.info("Alarm check daemon starting")
        check_for_and_play_notifications(datetime.now().astimezone())  # startup catch-up, don't wait for the first boundary

        while not self._stop_event.is_set():
            target_datetime = next_boundary(datetime.now().astimezone())
            prepare_at = target_datetime - timedelta(seconds=EARLY_WAKE_SECONDS)

            if self._interruptible_wait_until(prepare_at):
                break

            notification_files = check_for_notifications(target_datetime)

            if self._interruptible_wait_until(target_datetime):
                break

            if notification_files is not None:
                play_notification_files(notification_files)

        logger.info("Alarm check daemon stopped")


def run_daemon() -> None:
    AlarmCheckDaemon().run()
