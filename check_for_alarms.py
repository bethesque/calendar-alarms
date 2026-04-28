import logging
import os
import argparse
from datetime import datetime
from ecal.log_config import setup_logging_for_alarms
from ecal.env import DATA_DIRECTORY, LOG_LEVEL
from ecal.alarms.alarm import check_for_alarms
from ecal.calendar.google_calendar import CalendarSource

setup_logging_for_alarms(str(LOG_LEVEL))

logger = logging.getLogger(__name__)

def load_events(file_path):
    return CalendarSource(cache_file_path=file_path).load_data_from_file()


if __name__ == "__main__":
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
    base_time = args.base_time or datetime.now().astimezone()
    calendar_data = load_events(args.calendar_file)
    check_for_alarms(base_time, args.window, calendar_data)
