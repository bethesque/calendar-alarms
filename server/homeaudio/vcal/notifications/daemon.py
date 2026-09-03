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
from homeaudio.vcal.notifications.core import DATA_FILE, check_for_notifications

setup_logging_for_alarms(str(LOG_LEVEL))

logger = logging.getLogger(__name__)

CHECK_WINDOW_MINUTES = 5


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


def run_check(base_time: datetime) -> None:
    if not MainSettings().enabled:
        logger.info("Calendar Alarms are disabled in main settings; skipping this tick")
        return

    if not EventNotificationSettings().enabled:
        logger.info("Event notifications are disabled in settings; skipping this tick")
        return

    try:
        logger.info("Checking for alarms at %s", base_time)
        calendar_data = CalendarSource(cache_file_path=DATA_FILE).load_data_from_file()
        check_for_notifications(base_time, CHECK_WINDOW_MINUTES, calendar_data, scene_for_env())
    except Exception:
        # A single bad tick must never kill the loop - log and try again next boundary.
        logger.exception("Error checking for alarms at %s", base_time)


class AlarmCheckDaemon:
    def __init__(self):
        self._stop_event = threading.Event()

    def request_stop(self, *_args) -> None:
        logger.info("Shutdown requested; exiting after the current sleep")
        self._stop_event.set()

    def run(self) -> None:
        signal.signal(signal.SIGTERM, self.request_stop)
        signal.signal(signal.SIGINT, self.request_stop)

        logger.info("Alarm check daemon starting")
        run_check(datetime.now().astimezone())  # startup catch-up, don't wait for the first boundary

        while not self._stop_event.is_set():
            target = next_boundary(datetime.now().astimezone())
            remaining = (target - datetime.now().astimezone()).total_seconds()

            if remaining > 0 and self._stop_event.wait(timeout=remaining):
                break  # stop was requested during the sleep

            if self._stop_event.is_set():
                break

            run_check(target)

        logger.info("Alarm check daemon stopped")


def run_daemon() -> None:
    AlarmCheckDaemon().run()
