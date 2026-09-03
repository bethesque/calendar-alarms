import logging

from homeaudio.vcal.morning_announcements.core import play_morning_announcements_audio_file
from homeaudio.vcal.morning_announcements.core import MORNING_ANNOUNCEMENTS_AUDIO_FILE
from datetime import datetime
import argparse
from homeaudio.env import CALENDAR_DATA_DIRECTORY, LOG_LEVEL
import os
from homeaudio.vcal.morning_announcements.core import play_morning_announcements as do_play_morning_announcements, play_morning_announcements_audio_file
from homeaudio.audio.log_config import setup_logging_for_announcements
from homeaudio.audio.scene import scene_for_env
from homeaudio.audio.settings import MainSettings, MpdSettings, SnapcastSettings
from homeaudio.env import HOME_ASSISTANT_SUPPORTED

setup_logging_for_announcements(str(LOG_LEVEL))

logger = logging.getLogger(__name__)

def play_morning_announcements():
    if not MainSettings().enabled:
        logger.info("Calendar Alarms are disabled in main settings, exiting.")
        exit(0)

    parser = argparse.ArgumentParser(description="Check for alarms in calendar events")
    parser.add_argument(
        "--cached",
        action="store_true",
        help="Only announce cached events"
    )

    parser.add_argument(
        "--base_time",
        type=lambda s: datetime.fromisoformat(s),
        default=None,
        help="Base time for checking alarms (ISO format, defaults to current time)"
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

        if args.cached:
            play_morning_announcements_cached()
        else:
            do_play_morning_announcements(args.calendar_file, base_time, scene.prepare_for_alarm, scene.restore_after_alarm)
    except Exception:
        logger.exception("Error playing morning announcements")
        exit(1)


def play_morning_announcements_cached():
    scene = scene_for_env()

    play_morning_announcements_audio_file(MORNING_ANNOUNCEMENTS_AUDIO_FILE, SnapcastSettings(), MpdSettings(), scene.prepare_for_alarm, scene.restore_after_alarm)
