"""Computes car_departure_time for located calendar events from live traffic data via the
Google Maps Platform Routes API's computeRouteMatrix (TRAFFIC_AWARE), cached in
travel_time_cache.json. Only called from the calendar refresh pipeline."""

import json
import logging
import os
import re
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from typing import Callable

import requests

from homeaudio.audio.settings import DepartureNotificationSettings
from homeaudio.env import CALENDAR_DATA_DIRECTORY
from homeaudio.vcal.cal.google_calendar import Event

logger = logging.getLogger(__name__)

ROUTES_API_ENDPOINT = "https://routes.googleapis.com/distanceMatrix/v2:computeRouteMatrix"
TRAVEL_TIME_CACHE_FILE = os.path.join(CALENDAR_DATA_DIRECTORY, "travel_time_cache.json")

MAX_ITERATIONS = 4
CONVERGENCE_THRESHOLD = timedelta(minutes=1)
DEFAULT_TRIP_DURATION_GUESS = timedelta(minutes=30)

_TRAVEL_TAG_RE = re.compile(r"#travel(\d+)?")


class TravelTimeUnavailableError(Exception):
    """Raised when the Routes API responds but reports no route between the two addresses."""


def _rfc3339(dt: datetime) -> str:
    return dt.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def traffic_aware_duration(api_key: str, origin_address: str, destination_address: str, departure_time: datetime) -> timedelta:
    request_body = {
        "origins": [{"waypoint": {"address": origin_address}}],
        "destinations": [{"waypoint": {"address": destination_address}}],
        "travelMode": "DRIVE",
        "routingPreference": "TRAFFIC_AWARE",
        "departureTime": _rfc3339(departure_time),
    }
    headers = {
        "Content-Type": "application/json",
        "X-Goog-Api-Key": api_key,
        "X-Goog-FieldMask": "originIndex,destinationIndex,duration,distanceMeters,status,condition",
    }

    response = requests.post(ROUTES_API_ENDPOINT, json=request_body, headers=headers, timeout=10)
    try:
        response.raise_for_status()
    except requests.HTTPError:
        logger.error("Routes API error response: %s", response.text)
        raise

    elements = response.json()
    element = elements[0]
    if element.get("condition") != "ROUTE_EXISTS":
        raise TravelTimeUnavailableError(f"No route found from '{origin_address}' to '{destination_address}': {element}")

    duration_seconds = int(element["duration"].rstrip("s"))
    return timedelta(seconds=duration_seconds)


def solve_car_departure_time(
    target_arrival: datetime,
    cached_duration: timedelta | None,
    safety_factor: int,
    now: datetime,
    fetch_duration: Callable[[datetime], timedelta],
) -> tuple[datetime, timedelta] | None:
    departure_guess = target_arrival - (cached_duration if cached_duration is not None else DEFAULT_TRIP_DURATION_GUESS)

    last_duration: timedelta | None = None
    last_guess: datetime | None = None

    for _ in range(MAX_ITERATIONS):
        query_time = max(departure_guess, now)
        try:
            duration = fetch_duration(query_time)
        except Exception:
            logger.exception("Error fetching traffic-aware duration; falling back to the last successful estimate")
            break

        next_guess = target_arrival - duration
        last_duration = duration
        last_guess = next_guess

        converged = abs(next_guess - departure_guess) < CONVERGENCE_THRESHOLD
        departure_guess = next_guess
        if converged:
            break

    if last_guess is None or last_duration is None:
        return None

    padded_duration = last_duration + last_duration * safety_factor / 100
    car_departure_time = target_arrival - padded_duration
    return car_departure_time, last_duration


@dataclass
class TravelTimeCacheEntry:
    car_departure_time: datetime
    duration_seconds: float
    computed_at: datetime
    event_start_time: datetime
    location: str
    parking_minutes: int
    safety_factor: int

    @property
    def duration(self) -> timedelta:
        return timedelta(seconds=self.duration_seconds)

    def to_dict(self) -> dict:
        return {
            "car_departure_time": self.car_departure_time.isoformat(),
            "duration_seconds": self.duration_seconds,
            "computed_at": self.computed_at.isoformat(),
            "event_start_time": self.event_start_time.isoformat(),
            "location": self.location,
            "parking_minutes": self.parking_minutes,
            "safety_factor": self.safety_factor,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "TravelTimeCacheEntry":
        return cls(
            car_departure_time=datetime.fromisoformat(data["car_departure_time"]),
            duration_seconds=data["duration_seconds"],
            computed_at=datetime.fromisoformat(data["computed_at"]),
            event_start_time=datetime.fromisoformat(data["event_start_time"]),
            location=data["location"],
            parking_minutes=data["parking_minutes"],
            safety_factor=data["safety_factor"],
        )


@dataclass
class TravelTimeCache:
    cache_file_path: str = TRAVEL_TIME_CACHE_FILE
    entries: dict[str, TravelTimeCacheEntry] = field(default_factory=dict)

    @classmethod
    def load(cls, cache_file_path: str = TRAVEL_TIME_CACHE_FILE) -> "TravelTimeCache":
        if not os.path.exists(cache_file_path):
            return cls(cache_file_path=cache_file_path)

        with open(cache_file_path, "r") as f:
            raw = json.load(f)

        entries = {google_event_id: TravelTimeCacheEntry.from_dict(data) for google_event_id, data in raw.items()}
        return cls(cache_file_path=cache_file_path, entries=entries)

    def save(self) -> None:
        data = {google_event_id: entry.to_dict() for google_event_id, entry in self.entries.items()}
        with open(self.cache_file_path, "w") as f:
            json.dump(data, f, sort_keys=True)

    def get(self, google_event_id: str) -> TravelTimeCacheEntry | None:
        return self.entries.get(google_event_id)

    def set(self, google_event_id: str, entry: TravelTimeCacheEntry) -> None:
        self.entries[google_event_id] = entry

    def prune(self, now: datetime) -> None:
        self.entries = {
            google_event_id: entry
            for google_event_id, entry in self.entries.items()
            if entry.event_start_time >= now
        }


def _has_travel_tag(description: str | None) -> bool:
    return bool(description and _TRAVEL_TAG_RE.search(description))


def _is_in_scope(event: Event, now: datetime) -> bool:
    if not event.location:
        return False
    if event.start_time is None or event.start_time < now:
        return False
    if event.start_time.date() != now.date():
        return False
    if _has_travel_tag(event.description):
        return False
    return True


def _is_stale(entry: TravelTimeCacheEntry | None, event: Event, departure_notification_settings: DepartureNotificationSettings, now: datetime) -> bool:
    if entry is None:
        return True
    if entry.event_start_time != event.start_time:
        return True
    if entry.location != event.location:
        return True
    if entry.parking_minutes != departure_notification_settings.parking_minutes:
        return True
    if entry.safety_factor != departure_notification_settings.safety_factor:
        return True
    return now - entry.computed_at >= timedelta(minutes=departure_notification_settings.recompute_interval_minutes)


def car_departure_time_for_event(event: Event, departure_notification_settings: DepartureNotificationSettings, cache: TravelTimeCache, now: datetime) -> datetime | None:
    if not _is_in_scope(event, now):
        return event.car_departure_time

    if not event.google_event_id:
        logger.warning("Event '%s' has no google_event_id; cannot cache its travel time", event.summary)
        return event.car_departure_time

    cached_entry = cache.get(event.google_event_id)

    if not _is_stale(cached_entry, event, departure_notification_settings, now):
        return cached_entry.car_departure_time

    target_arrival = event.start_time - timedelta(minutes=departure_notification_settings.parking_minutes)
    cached_duration = cached_entry.duration if cached_entry else None

    result = solve_car_departure_time(
        target_arrival=target_arrival,
        cached_duration=cached_duration,
        safety_factor=departure_notification_settings.safety_factor,
        now=now,
        fetch_duration=lambda departure_time: traffic_aware_duration(
            departure_notification_settings.api_key, departure_notification_settings.origin_address, event.location, departure_time
        ),
    )

    if result is None:
        logger.warning("Could not compute a travel time for event '%s'; keeping the previous estimate", event.summary)
        return cached_entry.car_departure_time if cached_entry else event.car_departure_time

    car_departure_time, duration = result
    cache.set(event.google_event_id, TravelTimeCacheEntry(
        car_departure_time=car_departure_time,
        duration_seconds=duration.total_seconds(),
        computed_at=now,
        event_start_time=event.start_time,
        location=event.location,
        parking_minutes=departure_notification_settings.parking_minutes,
        safety_factor=departure_notification_settings.safety_factor,
    ))
    return car_departure_time
