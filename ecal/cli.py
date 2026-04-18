from ecal.env import DATA_DIRECTORY
from ecal.google_calendar import CalendarSource
from ecal.env import filter

"""
This script refreshes the calendar data and saves it to a local file. It is for dev and test only.
"""

DATA_FILE = DATA_DIRECTORY + "/calendar.json"

def refresh_calendar_data():
    print(f"Refreshing calendar data in {DATA_FILE}...")
    calendar_source = CalendarSource(stubbed=False, cache_file_path=DATA_FILE)
    calendar_source.load_creds()
    calendar_source.fetch_data(filter)
    calendar_source.save_data_to_file()
