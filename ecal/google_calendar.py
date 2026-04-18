from __future__ import print_function

import datetime
from zoneinfo import ZoneInfo
import os.path
from dataclasses import dataclass, field
from operator import attrgetter
import logging
import json
from ecal.string_utils import json_default_encoder
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError

# If modifying these scopes, delete the file token.json.
SCOPES = ["https://www.googleapis.com/auth/calendar.readonly"]
TIMEZONE = "Australia/Melbourne"

logger = logging.getLogger(__name__)


@dataclass
class GoogleCalendar:
    id: str
    name: str


@dataclass
class Event:
    owner: str
    summary: str
    description: str
    start_time: datetime.datetime = None
    end_time: datetime.datetime = None
    recurring: bool = False


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

def load_google_creds():
    creds = None
    # The file token.json stores the user's access and refresh tokens, and is
    # created automatically when the authorization flow completes for the first
    # time.
    token_filename = "token.json"
    if os.path.exists(token_filename):
        creds = Credentials.from_authorized_user_file(token_filename, SCOPES)

    if creds and creds.expired and creds.refresh_token:
        try:
            creds.refresh(Request())
        except:
            creds = None

    return creds


def list_google_calendars(creds):
    try:
        service = build("calendar", "v3", credentials=creds)
        result = service.calendarList().list().execute()
        return [GoogleCalendar(c["id"], c["summary"]) for c in result.get("items", [])]
    except HttpError as error:
        logger.error(f"An error occurred: {error}")
        return []


def list_google_events(creds, calendar_id, min, max):
    try:
        service = build("calendar", "v3", credentials=creds)
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


def add_events_to_calendars(events_from_google, calendar_name, displayed_calendar_days):
    for event_dict in events_from_google:

        matched_days = [d for d in displayed_calendar_days if displayed_day_includes_event(d, event_dict)]

        for matched_day in matched_days:
            event = build_event(event_dict, calendar_name)

            if "dateTime" in event_dict["start"]: # has a time specified
                event.start_time = datetime.datetime.fromisoformat(event_dict["start"]["dateTime"])
                matched_day.timed_events.append(event)
            else:
                matched_day.whole_day_events.append(event)


def is_weather_forecast(event_dict):
    return event_dict["summary"].startswith("Min ") or event_dict["summary"].startswith("Max ")


def build_event(event_dict, calendar_name):
    if is_weather_forecast(event_dict):
        return WeatherForecast(
            owner=calendar_name,
            summary=event_dict["summary"],
            description="",
        )
    else:
        return Event(
            owner=calendar_name,
            summary=event_dict["summary"],
            description=event_dict.get("description"),
            recurring=bool(event_dict.get("recurringEventId")),
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


def get_calendars(creds, filter):
    google_calendars = list_google_calendars(creds)
    google_calendars_by_id = {calendar.id: calendar for calendar in google_calendars}
    start_of_today = datetime.datetime.combine(
        datetime.date.today(), datetime.time.min, tzinfo=ZoneInfo(TIMEZONE)
    )
    tomorrow = start_of_today + datetime.timedelta(days=1)
    end_of_tomorrow = tomorrow + datetime.timedelta(days=1) - datetime.timedelta(seconds=1)
    displayed_calendar_days = [CalendarDay(date=start_of_today.date()), CalendarDay(date=tomorrow.date())]

    for cal_id, display_name in filter:
        gcal = google_calendars_by_id[cal_id]
        if gcal:
            events = list_google_events(
                creds,
                gcal.id,
                start_of_today,
                end_of_tomorrow,
            )
            logger.info(f"Adding events from id: {gcal.id} name: {gcal.name}")
            add_events_to_calendars(events, display_name, displayed_calendar_days)

    for cal in displayed_calendar_days:
        cal.timed_events.sort(key=attrgetter("start_time"))
    return displayed_calendar_days

# Load calendar data from a JSON file.
def load_data_from_file(file_path):
    with open(file_path, "r") as f:
        days = json.load(f)
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

    if is_weather_forecast(event_dict):
        return WeatherForecast(**event_args)
    else:
        return Event(**event_args)

def test_data():
    today = datetime.datetime.combine(
        datetime.date.today(), datetime.time.min, tzinfo=ZoneInfo(TIMEZONE)
    )
    tomorrow = today + datetime.timedelta(days=1)
    calendars = [CalendarDay(date=today.date()), CalendarDay(date=tomorrow.date())]
    today = calendars[0]
    tomorrow = calendars[1]
    forecast = "Min 11, Max 16, 1-8mm 90%, Showers, Windy"
    today.whole_day_events.append(WeatherForecast("BoM", forecast, ""))
    today.whole_day_events.append(Event("Trav", "Working on calendar epaper thing", "Once off event"))
    today.whole_day_events.append(Event("Trav", "A very important event", "#veryimportant", recurring=True))
    today.whole_day_events.append(Event("Trav", "A normal recurring event", "", recurring=True))
    today.whole_day_events.append(Event("Trav", "An important recurring event", "#important", recurring=True))
    today.whole_day_events.append(Event("Beth", "A once off unimportant event", "#notimportant", recurring=True))
    today.timed_events.append(
        Event(
            "Beth",
            "A very long summary that is going to take way more space than we have to fit in the calendar horizontally which will cause it to split across multiple lines",
            None,
            datetime.datetime(2023, 11, 2, 11, 30, tzinfo=ZoneInfo(TIMEZONE)),
        )
    )
    event_time = datetime.datetime(2023, 11, 3, 9, tzinfo=ZoneInfo(TIMEZONE))
    for n in range(10):
        tomorrow.timed_events.append(Event("B & T", f"fake event #{n}", None, event_time, recurring=True))
        event_time = event_time + datetime.timedelta(minutes=30)
    return calendars


@dataclass
class FakeCreds:
    valid: bool


@dataclass
class CalendarSource:
    stubbed: bool
    cache_file_path: str
    calendar_days: list = None
    creds: any = None

    def load_creds(self):
        if self.stubbed:
            self.creds = FakeCreds(valid=True)
        else:
            self.creds = load_google_creds()
        return self.creds

    def creds_valid(self):
        return self.creds and self.creds.valid

    def fetch_data(self, filter):
        if self.stubbed:
            self.calendar_days = test_data()
        else:
            self.calendar_days = get_calendars(self.creds, filter)
        return self.calendar_days

    def load_data_from_file(self):
        self.calendar_days = load_data_from_file(self.cache_file_path)
        return self.calendar_days

    def save_data_to_file(self):
        data_json = json.dumps(self.calendar_days, sort_keys=True, default=json_default_encoder)
        with open(self.cache_file_path, "w") as f:
            f.write(data_json)

    def cache_file_exists(self):
        return os.path.exists(self.cache_file_path)

