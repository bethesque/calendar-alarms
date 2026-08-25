from homeaudio.env import CALENDAR_DATA_DIRECTORY, LOG_LEVEL
from homeaudio.vcal.cal.google_calendar import CalendarSource
from homeaudio.vcal.cal.google_tasks import TaskSource
from homeaudio.audio.log_config import setup_logging_for_data_refresh
from homeaudio.audio.settings import GoogleCalendarSettings

"""
This script refreshes the calendar data and saves it to a local file.
"""

DATA_FILE = CALENDAR_DATA_DIRECTORY + "/calendar.json"
TASKS_DATA_FILE = CALENDAR_DATA_DIRECTORY + "/tasks.json"

setup_logging_for_data_refresh(str(LOG_LEVEL))

def refresh_calendar_data():

    print(f"Refreshing calendar data in {DATA_FILE}...")
    calendar_source = CalendarSource(cache_file_path=DATA_FILE)
    calendar_source.load_creds()
    calendar_source.fetch_data(GoogleCalendarSettings().calendar_filter())
    calendar_source.save_data_to_file()

def refresh_task_data():

    print(f"Refreshing today's tasks in {TASKS_DATA_FILE}...")
    task_source = TaskSource(cache_file_path=TASKS_DATA_FILE)
    task_source.load_creds()
    task_source.fetch_data()
    task_source.save_data_to_file()
