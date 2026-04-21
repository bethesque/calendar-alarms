import argparse
from ecal.env import DATA_DIRECTORY
import os
from ecal.announcements.announce import announce, play_morning_summary_announcement
from ecal.log_config import setup_logging_for_announcements

setup_logging_for_announcements()

if __name__ == "__main__":
    # add --cached option to only announce cached events
    parser = argparse.ArgumentParser(description="Check for alarms in calendar events")
    parser.add_argument(
        "--cached",
        action="store_true",
        help="Only announce cached events"
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

    if args.cached:
        play_morning_summary_announcement()
    else:
        announce(args.calendar_file)
