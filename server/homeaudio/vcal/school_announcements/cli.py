import logging

from datetime import datetime
import argparse
from homeaudio.vcal.school_announcements.core import play_school_announcements as do_play_school_announcements
from homeaudio.env import CALENDAR_DATA_DIRECTORY, LOG_LEVEL
import os
from homeaudio.audio.log_config import setup_logging_for_announcements
from homeaudio.audio.scene import scene_for_env
from homeaudio.audio.settings import MainSettings, SchoolAnnouncementsSettings

setup_logging_for_announcements(str(LOG_LEVEL))

logger = logging.getLogger(__name__)

def play_school_announcements():
    if not MainSettings().enabled:
        logger.info("Calendar Alarms are disabled in main settings, exiting.")
        exit(0)

    parser = argparse.ArgumentParser(description="Announce today's school events")

    parser.add_argument(
        "--base_time",
        type=lambda s: datetime.fromisoformat(s),
        default=None,
        help="Base time for checking events (ISO format, defaults to current time)"
    )

    parser.add_argument(
        "--calendar_file",
        default=os.path.join(CALENDAR_DATA_DIRECTORY, "calendar.json"),
        help=f"Path to the calendar JSON file (default: {os.path.join(CALENDAR_DATA_DIRECTORY, 'calendar.json')})"
    )

    args = parser.parse_args()

    try:
        base_time = args.base_time or datetime.now().astimezone()

        scene = scene_for_env()

        do_play_school_announcements(args.calendar_file, base_time, SchoolAnnouncementsSettings(), scene.prepare_for_alarm, scene.restore_after_alarm)
    except Exception:
        logger.exception("Error playing school announcements")
        exit(1)
