import logging
import logging
import os
import argparse
import yaml
from datetime import datetime
from homeaudio.env import LOG_LEVEL
from homeaudio.audio.mpd import fade_out, fade_up, mpd_connection
from homeaudio.audio.log_config import setup_logging_for_alarms
from homeaudio.vcal.cal.google_calendar import CalendarSource, CalendarDay
from homeaudio.audio.scene import scene_for_env
from homeaudio.audio.settings import MainSettings

from homeaudio.env import CALENDAR_DATA_DIRECTORY, HOME_ASSISTANT_SUPPORTED
from homeaudio.vcal.event_notifications.core import check_for_and_play_notifications
from homeaudio.vcal.event_notifications.events import get_all_event_notifications

setup_logging_for_alarms(str(LOG_LEVEL))

logger = logging.getLogger(__name__)

def load_calendar_days(file_path) -> list[CalendarDay]:
    return CalendarSource(cache_file_path=file_path).load_data_from_file()

def check_alarms():
    if not MainSettings().enabled:
        logger.info("Calendar Alarms are disabled in main settings, exiting.")
        exit(0)

    parser = argparse.ArgumentParser(description="Check for alarms in calendar events")
    parser.add_argument(
        "--base_time",
        type=lambda s: datetime.fromisoformat(s),
        default=None,
        help="Base time for checking alarms (ISO format, defaults to current time)"
    )
    parser.add_argument(
        "--window",
        type=int,
        default=5,
        help="Time window in minutes for checking alarms (default: 5)"
    )

    parser.add_argument(
        "--calendar_file",
        default=os.path.join(CALENDAR_DATA_DIRECTORY, "calendar.json"),
        help=f"Path to the calendar JSON file (default: {os.path.join(CALENDAR_DATA_DIRECTORY, 'calendar.json')})"
    )

    args = parser.parse_args()

    try:
        logger.info(f"Checking for alarms in {args.calendar_file}...")

        base_time = args.base_time or datetime.now().astimezone()
        calendar_data = load_calendar_days(args.calendar_file)

        check_for_and_play_notifications(base_time, args.window, calendar_data, scene_for_env())
    except Exception:
        logger.exception("Error checking for alarms")
        exit(1)
