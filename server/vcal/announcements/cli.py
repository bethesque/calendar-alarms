from vcal.announcements.announce import play_morning_announcements_audio_file, MORNING_ANNOUNCEMENTS_AUDIO_FILE
from datetime import datetime
import argparse
from vcal.env import DATA_DIRECTORY, LOG_LEVEL
import os
from vcal.announcements.announce import play_morning_announcements as do_play_morning_announcements, play_morning_announcements_audio_file, SPEECH_FILE
from vcal.log_config import setup_logging_for_announcements
from vcal.scene import Scene2
from vcal.announcements.announce import play_announcement as play_announcement_func

setup_logging_for_announcements(str(LOG_LEVEL))

def play_announcement():
    parser = argparse.ArgumentParser(description="Play a one-off announcement")
    parser.add_argument(
        "--message",
        help="The message to announce"
    )
    args = parser.parse_args()
    print(f"Playing announcement: {args.message}")
    play_announcement_func(args.message, Scene2())

def play_morning_announcements():
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
        default=os.path.join(DATA_DIRECTORY, "calendar.json"),
        help=f"Path to the calendar JSON file (default: {os.path.join(DATA_DIRECTORY, 'calendar.json')})"
    )

    args = parser.parse_args()
    base_time = args.base_time or datetime.now().astimezone()

    scene = Scene2()
    scene.save()

    if args.cached:
        play_morning_announcements_cached()
    else:
        do_play_morning_announcements(args.calendar_file, base_time, scene.prepare_for_alarm, scene.restore_after_alarm)


def play_morning_announcements_cached():
    scene = Scene2()
    scene.save()
    play_morning_announcements_audio_file(MORNING_ANNOUNCEMENTS_AUDIO_FILE, scene.prepare_for_alarm, scene.restore_after_alarm)
