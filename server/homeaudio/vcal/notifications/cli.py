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
from homeaudio.audio.scene import NullScene, HomeAssistantScene
from homeaudio.audio.settings import MainSettings

from homeaudio.env import CALENDAR_DATA_DIRECTORY, HOME_ASSISTANT_SUPPORTED
from homeaudio.vcal.notifications.core import check_for_notifications, get_all_event_notifications

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

        scene = HomeAssistantScene() if HOME_ASSISTANT_SUPPORTED else NullScene()

        check_for_notifications(base_time, args.window, calendar_data, scene)
    except Exception:
        logger.exception("Error checking for alarms")
        exit(1)

def stop_alarm():
    try:
        with mpd_connection() as alarm_player:
            fade_out([alarm_player], 3)
            logger.info("Alarm stopped.")
    except Exception as e:
        logger.error(f"Error stopping alarm: {e}")
        exit(1)

def play_test_file():
    # get audio file path from the command line argument
    parser = argparse.ArgumentParser(description="Play a test audio file")
    parser.add_argument(
        "audio_file",
        help="Path to the audio file to play"
    )
    args = parser.parse_args()
    audio_file = args.audio_file

    try:
        # Play the mixed audio file
        with mpd_connection() as alarm_player:
            alarm_player.set_volume(60)
            alarm_player.play_file(audio_file)
            fade_up([(alarm_player, 80)], 5, 10)
    except Exception as e:
        logger.error(f"Error playing alarm: {e}")
        exit(1)

def list_notifications():
    print(yaml.dump(get_all_event_notifications(), default_flow_style=False, sort_keys=False))
