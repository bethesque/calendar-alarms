"""Refreshes calendar data from Google Calendar on its own schedule and thread, independent of
the notification loop in daemon.py, so a slow or failing Google API call never delays a
notification prepare/play tick.
"""

import logging
import threading
from datetime import date, datetime, timedelta

from homeaudio.audio.settings import (
    EventNotificationSchedule,
    EventNotificationSettings,
    MorningAnnouncementsSchedule,
    MorningAnnouncementsSettings,
    SchoolAnnouncementsSchedule,
    SchoolAnnouncementsSettings,
    TimeRange,
)
from homeaudio.vcal.cli import refresh_calendar_data as fetch_and_save_calendar_data
from homeaudio.vcal.notification_schedule import announcement_times_for_day, event_notification_time_range_for_day

logger = logging.getLogger(__name__)

# How often this loop re-fetches from Google Calendar, and how far past each
# REFRESH_INTERVAL_MINUTES-aligned minute it runs. Calendar events - and so alarms/announcements -
# usually land on the 5-minute mark, so the offset keeps refreshes a few minutes clear of whatever
# is actually playing there, rather than starting a Google Calendar request while both loops
# contend for the one CPU core on the smallest deployment target (a Raspberry Pi Zero W). Also
# doubles as the lead time this loop opens its window before the day's earliest trigger (see
# _wake_window_for_day) - one refresh interval's worth of buffer is exactly enough to guarantee
# the day's first refresh has landed before whichever notification-loop tick reads calendar.json
# first.
REFRESH_INTERVAL_MINUTES = 5
REFRESH_OFFSET_SECONDS = 3 * 60 + 15  # 3 minutes and 15 seconds

# The longest next_refresh_boundary() will ever ask this loop to sleep in one go, so a schedule
# change saved through the admin UI mid-sleep is noticed within the hour instead of only once a
# long, already-stale overnight wait finally ends.
MAX_SLEEP_SECONDS = 60 * 60 # 1 hour


def _wake_window_for_day(
    day: date,
    schedule: EventNotificationSchedule,
    morning_schedule: MorningAnnouncementsSchedule,
    school_schedule: SchoolAnnouncementsSchedule,
) -> TimeRange:
    """EventNotificationSettings.schedule's operating hours for `day`, widened at either end to
    cover any morning/school announcement scheduled outside it, and opened 3 * REFRESH_INTERVAL_MINUTES
    before the earliest of those - room for a couple of retries on top of the day's first refresh,
    in case one fails, while still landing well before whichever notification fires first."""
    base = event_notification_time_range_for_day(schedule, day)
    boundary_times = [base.start, base.end, *announcement_times_for_day(day, morning_schedule, school_schedule)]
    start = (datetime.combine(day, min(boundary_times)) - timedelta(minutes=3 * REFRESH_INTERVAL_MINUTES)).time()
    return TimeRange(start=start, end=max(boundary_times))


def next_refresh_boundary(
    now: datetime,
    schedule: EventNotificationSchedule | None = None,
    morning_schedule: MorningAnnouncementsSchedule | None = None,
    school_schedule: SchoolAnnouncementsSchedule | None = None,
) -> datetime:
    """The next REFRESH_INTERVAL_MINUTES-aligned time at or after `now`, offset by
    REFRESH_OFFSET_SECONDS so it stays clear of the 5-minute marks calendar events (and so
    alarms/announcements) usually land on - restricted to EventNotificationSettings.schedule's
    operating hours for that day,
    widened to cover any MorningAnnouncementsSettings/SchoolAnnouncementsSettings scheduled time
    that falls outside it, and opened 3 * REFRESH_INTERVAL_MINUTES before the earliest of those so
    a couple of failed refresh attempts still leave time for one to land before whichever
    notification-loop tick reads calendar.json first.

    Each schedule is read fresh from its settings by default, same as daemon.py's own
    next_boundary(), so a change saved through the admin UI takes effect on this loop's very next
    wake-up. Also capped by MAX_SLEEP_SECONDS for the same reason: a schedule change saved
    mid-sleep is noticed within the hour rather than only once an already-stale overnight wait
    finally ends.
    """
    schedule = schedule or EventNotificationSettings().schedule
    morning_schedule = morning_schedule or MorningAnnouncementsSettings().schedule
    school_schedule = school_schedule or SchoolAnnouncementsSettings().schedule

    floor_minute = (now.minute // REFRESH_INTERVAL_MINUTES) * REFRESH_INTERVAL_MINUTES
    candidate = now.replace(minute=0, second=0, microsecond=0) + timedelta(
        minutes=floor_minute, seconds=REFRESH_OFFSET_SECONDS
    )
    if candidate <= now:
        candidate += timedelta(minutes=REFRESH_INTERVAL_MINUTES)

    while True:
        window = _wake_window_for_day(candidate.date(), schedule, morning_schedule, school_schedule)
        if window.start <= candidate.time() < window.end:
            break
        offset = timedelta(seconds=REFRESH_OFFSET_SECONDS)
        if candidate.time() < window.start:
            candidate = datetime.combine(candidate.date(), window.start, tzinfo=candidate.tzinfo) + offset
        else:
            next_day = candidate.date() + timedelta(days=1)
            next_window = _wake_window_for_day(next_day, schedule, morning_schedule, school_schedule)
            candidate = datetime.combine(next_day, next_window.start, tzinfo=candidate.tzinfo) + offset

    return min(candidate, now + timedelta(seconds=MAX_SLEEP_SECONDS))


def refresh_calendar(base_time: datetime) -> None:
    """Fetches fresh calendar data from Google and writes it to the cache file the notification
    loop reads from."""
    try:
        logger.info("Refreshing calendar data at %s", base_time)
        fetch_and_save_calendar_data()
    except Exception:
        # A single bad refresh must never kill the loop - log and try again next boundary.
        logger.exception("Error refreshing calendar data at %s", base_time)


class CalendarRefreshLoop:
    """Runs refresh_calendar() on REFRESH_INTERVAL_MINUTES, on its own daemon thread. Takes the
    stop_event of whatever owns it (rather than creating its own) so both loops start and stop
    together."""

    def __init__(self, stop_event: threading.Event):
        self._stop_event = stop_event

    def start(self) -> threading.Thread:
        thread = threading.Thread(target=self._run, name="calendar-refresh", daemon=True)
        thread.start()
        return thread

    def _run(self) -> None:
        logger.info("Starting calendar data refresh thread")
        while not self._stop_event.is_set():
            refresh_at = next_refresh_boundary(datetime.now().astimezone())
            remaining = (refresh_at - datetime.now().astimezone()).total_seconds()
            logger.info(f"Sleeping for {remaining:.2f} seconds until {refresh_at}")
            if remaining > 0 and self._stop_event.wait(timeout=remaining):
                break
            if self._stop_event.is_set():
                break

            refresh_calendar(refresh_at)

        logger.info("Stopping calendar data refresh thread")


