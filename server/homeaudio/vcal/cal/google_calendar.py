from __future__ import print_function

import datetime

from typing import Any
from zoneinfo import ZoneInfo
import os.path
from dataclasses import dataclass, field

from operator import attrgetter
import logging
import json
from homeaudio.audio.string_utils import json_default_encoder
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError

from homeaudio.env import CALENDAR_DATA_DIRECTORY


SCOPES = ["https://www.googleapis.com/auth/calendar.readonly"]
DATA_FILE = CALENDAR_DATA_DIRECTORY + "/calendar.json"
DAYS_TO_FETCH = 7

TIMEZONE = "Australia/Melbourne"

logger = logging.getLogger(__name__)

class MissingCalendarDataException(Exception):
    pass

@dataclass
class GoogleCalendar:
    id: str
    name: str

@dataclass
class Event:
    owner: str
    calendar_id: str
    summary: str
    description: str
    start_time: datetime.datetime = None
    end_time: datetime.datetime = None
    recurring: bool = False
    owner_count: int = 0
    location: str | None = None
    google_event_id: str | None = None
    car_departure_time: datetime.datetime | None = None

@dataclass
class WeatherForecast(Event):
    recurring: bool = True


# A day displayed on the calendar screen
@dataclass
class CalendarDay:
    date: datetime.date
    whole_day_events: list[Event] = field(default_factory=list)
    timed_events: list[Event] = field(default_factory=list)
    date_time: datetime.datetime = None

    def __post_init__(self):
        self.date_time = datetime.datetime.combine(self.date, datetime.time.min, tzinfo=ZoneInfo(TIMEZONE))

    def all_events(self):
        return self.whole_day_events + self.timed_events

def load_google_creds(token_info: dict | None):
    creds = None

    if token_info:
        creds = Credentials.from_authorized_user_info(token_info, SCOPES)

    if creds and creds.expired and creds.refresh_token:
        try:
            creds.refresh(Request())
        except:
            creds = None

    return creds


def list_google_calendars(creds):
    try:
        service = build("calendar", "v3", credentials=creds, cache_discovery=False)
        result = service.calendarList().list().execute()
        return [GoogleCalendar(c["id"], c["summary"]) for c in result.get("items", [])]
    except HttpError as error:
        logger.error(f"An error occurred: {error}")
        return []


def list_google_events(creds, calendar_id, min, max):
    try:
        service = build("calendar", "v3", credentials=creds, cache_discovery=False)
        events_result = (
            service.events()
            .list(
                calendarId=calendar_id,
                timeMin=min.isoformat(),
                timeMax=max.isoformat(),
                singleEvents=True,
                orderBy="startTime",
            )
            .execute()
        )
        events = events_result.get("items", [])
        return [e for e in events if e.get("visibility") != "private"]

    except HttpError as error:
        logger.info("An error occurred: %s" % error)
        return []


def add_events_to_calendars(events_from_google, calendar_id, calendar_name, displayed_calendar_days, owner_count):
    for event_dict in events_from_google:

        matched_days = [d for d in displayed_calendar_days if displayed_day_includes_event(d, event_dict)]

        for matched_day in matched_days:
            event = event_from_google_dict(event_dict, calendar_id, calendar_name, owner_count)

            if "dateTime" in event_dict["start"]: # has a time specified
                event.start_time = datetime.datetime.fromisoformat(event_dict["start"]["dateTime"])
                matched_day.timed_events.append(event)
            else:
                matched_day.whole_day_events.append(event)


def is_weather_forecast(event_dict):
    return event_dict["summary"].startswith("Min ") or event_dict["summary"].startswith("Max ")


def event_from_google_dict(event_dict, calendar_id, calendar_name, owner_count):
    if is_weather_forecast(event_dict):
        return WeatherForecast(
            owner=calendar_name,
            calendar_id=calendar_id,
            owner_count=0,
            summary=event_dict["summary"],
            description="",
        )
    else:
        return Event(
            owner=calendar_name,
            calendar_id=calendar_id,
            owner_count=owner_count,
            summary=event_dict["summary"],
            description=event_dict.get("description"),
            recurring=bool(event_dict.get("recurringEventId")),
            location=event_dict.get("location", None),
            google_event_id=event_dict.get("id"),
        )


"""
Returns true if the event described by the properties in the event_dict falls on the date
of the given displayed CalendarDay.

Properties:

event_dict: dict
    The Google Calendar event dict.
"""
def displayed_day_includes_event(displayed_calendar_day, event_dict):
    start = event_dict["start"] # dict with either "date" or "dateTime" as a string
    start_date_text = start.get("date", start.get("dateTime"))
    start_date = datetime.datetime.fromisoformat(start_date_text).date()

    end = event_dict["end"] # dict with either "date" or "dateTime" as a string
    end_date_text = end.get("date", end.get("dateTime"))
    end_date_time = datetime.datetime.fromisoformat(end_date_text)

    if end_date_time.tzinfo is None:
        end_date_time = end_date_time.replace(tzinfo=ZoneInfo(TIMEZONE))

    return displayed_calendar_day.date == start_date or ( start_date < displayed_calendar_day.date and displayed_calendar_day.date_time < end_date_time )


def get_calendar_days(creds, filter):
    google_calendars = list_google_calendars(creds)
    google_calendars_by_id = {calendar.id: calendar for calendar in google_calendars}
    start_of_today = datetime.datetime.combine(
        datetime.date.today(), datetime.time.min, tzinfo=ZoneInfo(TIMEZONE)
    )
    end_of_period = start_of_today + datetime.timedelta(days=DAYS_TO_FETCH) - datetime.timedelta(seconds=1)
    displayed_calendar_days = [
        CalendarDay(date=(start_of_today + datetime.timedelta(days=offset)).date())
        for offset in range(DAYS_TO_FETCH)
    ]

    for cal_id, display_name, owner_count in filter:
        gcal = google_calendars_by_id[cal_id]
        if gcal:
            events = list_google_events(
                creds,
                gcal.id,
                start_of_today,
                end_of_period,
            )
            logger.info(f"Adding events from id: {gcal.id} name: {gcal.name}")
            add_events_to_calendars(events, cal_id, display_name, displayed_calendar_days, owner_count)

    for cal in displayed_calendar_days:
        cal.timed_events.sort(key=attrgetter("start_time"))
    return displayed_calendar_days

def load_data_from_any(days: Any) -> list[CalendarDay]:
        calendar_days = []
        for day in days:
            whole_day_events = [load_event(event) for event in day["whole_day_events"]]
            timed_events = [load_event(event) for event in day["timed_events"]]
            calendar_day = CalendarDay(
                date=datetime.date.fromisoformat(day["date"]),
                whole_day_events=whole_day_events,
                timed_events=timed_events,
            )
            calendar_days.append(calendar_day)
        return calendar_days

# Load event from dict from a JSON file
def load_event(event_dict):
    event_args = { **event_dict }

    if event_args.get("start_time"):
        event_args["start_time"] = datetime.datetime.fromisoformat(event_args.get("start_time"))

    if event_args.get("end_time"):
        event_args["end_time"] = datetime.datetime.fromisoformat(event_args.get("end_time"))

    if event_args.get("car_departure_time"):
        event_args["car_departure_time"] = datetime.datetime.fromisoformat(event_args.get("car_departure_time"))

    if is_weather_forecast(event_dict):
        return WeatherForecast(**event_args)
    else:
        return Event(**event_args)


def get_events_for_date(calendar_days, date_time):
    match = next((day for day in calendar_days if day.date == date_time.date()), None)
    if match:
        return match.all_events()
    else:
        available_dates = [str(day.date) for day in calendar_days]
        raise MissingCalendarDataException(f"Could not find day matching {str(date_time.date())} in days with dates: {available_dates}")

@dataclass
class CalendarSource:
    cache_file_path: str = DATA_FILE
    calendar_days: list = None
    creds: any = None
    refreshed_at: datetime.datetime | None = None

    def load_creds(self, token_info: dict | None):
        self.creds = load_google_creds(token_info)
        return self.creds

    def creds_valid(self):
        return self.creds and self.creds.valid

    def fetch_data(self, filter):
        self.calendar_days = get_calendar_days(self.creds, filter)
        self.refreshed_at = datetime.datetime.now().astimezone()
        return self.calendar_days

    def load_data_from_file(self) -> list[CalendarDay]:
        with open(self.cache_file_path, "r") as f:
            data = json.load(f)

        if isinstance(data, dict):  # new format
            self.refreshed_at = datetime.datetime.fromisoformat(data["refreshed_at"]) if data.get("refreshed_at") else None
            events = data["events"]
        else:  # old format was a bare array, with no refreshed_at
            self.refreshed_at = None
            events = data

        self.calendar_days = load_data_from_any(events)
        return self.calendar_days

    def load_data_from_any(self, any: Any) -> list[CalendarDay]:
        self.calendar_days = load_data_from_any(any)
        return self.calendar_days

    def save_data_to_file(self):
        data = {
            "events": self.calendar_days,
            "refreshed_at": self.refreshed_at,
        }
        data_json = json.dumps(data, sort_keys=True, default=json_default_encoder)
        with open(self.cache_file_path, "w") as f:
            f.write(data_json)

    def file_exists(self) -> bool:
        return os.path.exists(self.cache_file_path)
