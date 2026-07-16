from __future__ import print_function

import datetime
import re
from typing import Any
from zoneinfo import ZoneInfo
import os.path
from dataclasses import dataclass, field
from enum import Enum
from operator import attrgetter
import logging
import json
from vcal.string_utils import json_default_encoder
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError
from vcal.settings import GoogleCalendarSettings, NotificationRule

TIMEZONE = "Australia/Melbourne"

logger = logging.getLogger(__name__)

class MissingCalendarDataException(Exception):
    pass

@dataclass
class GoogleCalendar:
    id: str
    name: str

class NotificationType(Enum):
    ALARM = 1
    ANNOUNCE = 2

@dataclass
class EventNotification:
    event: "Event"
    type: NotificationType
    offset: int
    notification_time: datetime.datetime = field(init=False)

    def __post_init__(self):
        self.notification_time = self.event.start_time - datetime.timedelta(minutes=self.offset)


def notifications_from_description_rules(event: "Event", rules: list[NotificationRule]) -> list[EventNotification]:
    notifications: list[EventNotification] = []
    if not event.start_time or not event.description:
        return notifications

    description = event.description
    for rule in rules:
        if rule.owner is not None and rule.owner != "" and event.owner.lower() != rule.owner.lower():
            continue

        haystack = description.lower()
        needle = rule.pattern.lower()
        if needle in haystack:
            notifications.append(EventNotification(
                event=event,
                type=NotificationType[rule.notification_type.upper()],
                offset=rule.offset_minutes,
            ))
    return notifications

@dataclass
class Event:
    owner: str
    summary: str
    description: str
    start_time: datetime.datetime = None
    end_time: datetime.datetime = None
    recurring: bool = False

    def notifications(self, rules: list[NotificationRule] | None = None) -> list[EventNotification]:
        notifications = []
        if self.description and self.start_time:
            matches = re.findall(r"#(alarm|announce)(\d+)?", self.description)
            if matches:
                for match in matches:
                    type, offset = match
                    type_enum = NotificationType[type.upper()]
                    offset_int = int(offset) if offset else 0
                    notifications.append(EventNotification(type=type_enum, offset=offset_int, event=self))

        if rules:
            notifications.extend(notifications_from_description_rules(self, rules))

        return notifications

    def notifications_within_window(self, start_time, end_time, rules: list[NotificationRule] | None = None):
        notifications_in_window = []
        for event_notification in self.notifications(rules):
            if start_time <= event_notification.notification_time < end_time:
                notifications_in_window.append(event_notification)
        return notifications_in_window

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
    settings = GoogleCalendarSettings()
    token_filename = "token.json"
    if os.path.exists(token_filename):
        creds = Credentials.from_authorized_user_file(token_filename, [settings.scope])

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
def load_data_from_file(file_path: str) -> list[CalendarDay]:
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


def get_events_for_date(calendar_days, date_time):
    match = next((day for day in calendar_days if day.date == date_time.date()), None)
    if match:
        return match.all_events()
    else:
        raise MissingCalendarDataException()

@dataclass
class CalendarSource:
    cache_file_path: str
    calendar_days: list = None
    creds: any = None

    def load_creds(self):
        self.creds = load_google_creds()
        return self.creds

    def creds_valid(self):
        return self.creds and self.creds.valid

    def fetch_data(self, filter):

        self.calendar_days = get_calendars(self.creds, filter)
        return self.calendar_days

    def load_data_from_file(self) -> list[CalendarDay]:
        self.calendar_days = load_data_from_file(self.cache_file_path)
        return self.calendar_days

    def save_data_to_file(self):
        data_json = json.dumps(self.calendar_days, sort_keys=True, default=json_default_encoder)
        with open(self.cache_file_path, "w") as f:
            f.write(data_json)

    def cache_file_exists(self):
        return os.path.exists(self.cache_file_path)

