from datetime import datetime, timedelta

from homeaudio.env import CALENDAR_DATA_DIRECTORY, LOG_LEVEL
from homeaudio.vcal.cal.google_calendar import CalendarSource, Event
from homeaudio.audio.log_config import setup_logging_for_data_refresh
from homeaudio.audio.settings import GoogleCalendarSettings

"""
This script refreshes the calendar data and saves it to a local file.
"""

DATA_FILE = CALENDAR_DATA_DIRECTORY + "/calendar.json"

setup_logging_for_data_refresh(str(LOG_LEVEL))

def refresh_calendar_data():

    print(f"Refreshing calendar data in {DATA_FILE}...")
    calendar_source = CalendarSource(cache_file_path=DATA_FILE)
    calendar_source.load_creds()
    calendar_source.fetch_data(GoogleCalendarSettings().calendar_filter())
    calendar_source.save_data_to_file()


def insert_test_event():
    calendar_source = CalendarSource(cache_file_path=DATA_FILE)
    calendar_days = calendar_source.load_data_from_file()
    # find the calendar day for the current date
    today = next(day for day in calendar_days if day.date == datetime.now().date())
    start_time = datetime.now().astimezone() + timedelta(minutes=1)
    end_time = datetime.now().astimezone() + timedelta(minutes=30)
    event = Event(
        summary="A dynamically inserted test event",
        description="#announce",
        calendar_id="1",
        start_time=start_time,
        end_time=end_time,
        recurring=False,
        location=None,
        owner="Beth",
        owner_count=1,
    )
    today.timed_events.append(event)
    calendar_source.save_data_to_file()


