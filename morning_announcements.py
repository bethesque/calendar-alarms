from datetime import datetime
import argparse
from ecal.env import DATA_DIRECTORY, LOG_LEVEL
import os
from ecal.announcements.announce import announce, play_morning_announcements_audio_file
from ecal.log_config import setup_logging_for_announcements

setup_logging_for_announcements(str(LOG_LEVEL))

if __name__ == "__main__":
    # add --cached option to only announce cached events
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

    if args.cached:
        play_morning_announcements_audio_file()
    else:
        announce(args.calendar_file)
