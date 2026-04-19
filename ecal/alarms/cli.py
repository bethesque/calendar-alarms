import logging

from ecal.alarms.alarm import play_alarm
from ecal.alarms import ALARM_SOCKET, ANNOUNCEMENT_SOCKET, MIXED_SOCKET
from ecal.alarms.mpv import MpvProcess, fade_out, fade_up
from ecal.log_config import setup_logging
from ecal.env import SINGLE_STREAM

setup_logging(logging.DEBUG)

logger = logging.getLogger(__name__)

import json
import logging
import os
import argparse
from datetime import datetime
from ecal.log_config import setup_logging
from ecal.env import DATA_DIRECTORY
from ecal.alarms.alarm import check_for_alarms

setup_logging()

logger = logging.getLogger(__name__)

def load_events(file_path):
    with open(file_path, "r") as f:
        return json.load(f)

def check_alarms():
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
        default=os.path.join(DATA_DIRECTORY, "calendar.json"),
        help=f"Path to the calendar JSON file (default: {os.path.join(DATA_DIRECTORY, 'calendar.json')})"
    )
    args = parser.parse_args()

    logger.info(f"Checking for alarms in {args.calendar_file}...")

    base_time = args.base_time or datetime.now().astimezone()
    calendar_data = load_events(args.calendar_file)
    check_for_alarms(base_time, args.window, calendar_data)


def test_alarm():
    try:
        print("Testing alarm... press Ctrl+C to stop")
        play_alarm(["audio/test_announcement.mp3"])
    except KeyboardInterrupt as e:
        alarm_player = MpvProcess(ALARM_SOCKET)
        announcement_player = MpvProcess(ANNOUNCEMENT_SOCKET)
        fade_out([alarm_player, announcement_player], 3)
        exit(0)

def stop_alarm():
    try:
        mixed_player = MpvProcess(MIXED_SOCKET)
        alarm_player = MpvProcess(ALARM_SOCKET)
        announcement_player = MpvProcess(ANNOUNCEMENT_SOCKET)
        fade_out([alarm_player, announcement_player, mixed_player], 3)
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
        alarm_player = MpvProcess(MIXED_SOCKET)
        alarm_player.start()

        if not alarm_player.wait_for_ipc(timeout=30.0):
            logger.error(f"Error: mpv IPC socket at {MIXED_SOCKET} not ready")
            exit(1)

        alarm_player.set_volume(60)
        alarm_player.play_file(audio_file)
        fade_up([(alarm_player, 100)], 45, 10)
    except Exception as e:
        logger.error(f"Error playing alarm: {e}")
        exit(1)
