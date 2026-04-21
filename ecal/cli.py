from ecal.env import DATA_DIRECTORY
from ecal.google_calendar import CalendarSource
from ecal.env import filter
from ecal.log_config import setup_logging_for_data_refresh

"""
This script refreshes the calendar data and saves it to a local file.
"""

DATA_FILE = DATA_DIRECTORY + "/calendar.json"

setup_logging_for_data_refresh()

def refresh_calendar_data():
    print(f"Refreshing calendar data in {DATA_FILE}...")
    calendar_source = CalendarSource(stubbed=False, cache_file_path=DATA_FILE)
    calendar_source.load_creds()
    calendar_source.fetch_data(filter)
    calendar_source.save_data_to_file()
