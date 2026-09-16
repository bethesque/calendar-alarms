import json
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

import pytest
import requests

from homeaudio.audio.settings import DepartureNotificationSettings
from homeaudio.vcal.cal.google_calendar import Event
from homeaudio.vcal.departure_time import (
    CONVERGENCE_THRESHOLD,
    DEFAULT_TRIP_DURATION_GUESS,
    MAX_ITERATIONS,
    TravelTimeCache,
    TravelTimeCacheEntry,
    TravelTimeUnavailableError,
    car_departure_time_for_event,
    solve_car_departure_time,
    traffic_aware_duration,
)

TIMEZONE = ZoneInfo("Australia/Melbourne")


def _settings(**overrides) -> DepartureNotificationSettings:
    defaults = dict(
        api_key="fake-api-key",
        origin_address="1 Origin St",
        parking_minutes=5,
        house_to_car_minutes=5,
        safety_factor=10,
        heads_up_reminder_lead_time=5,
        recompute_interval_minutes=20,
    )
    defaults.update(overrides)
    return DepartureNotificationSettings(**defaults)


class _FakeResponse:
    def __init__(self, payload, status_code=200, text=""):
        self._payload = payload
        self.status_code = status_code
        self.text = text

    def raise_for_status(self):
        if self.status_code >= 400:
            raise requests.HTTPError(f"HTTP {self.status_code}")

    def json(self):
        return self._payload


def _route_response(duration_seconds: int):
    return [{"originIndex": 0, "destinationIndex": 0, "duration": f"{duration_seconds}s", "condition": "ROUTE_EXISTS"}]


# --- traffic_aware_duration --------------------------------------------------------------

def test_traffic_aware_duration_parses_seconds_from_response(monkeypatch):
    captured = {}

    def fake_post(url, json, headers, timeout):
        captured["url"] = url
        captured["json"] = json
        captured["headers"] = headers
        return _FakeResponse(_route_response(1800))

    monkeypatch.setattr("homeaudio.vcal.departure_time.requests.post", fake_post)

    duration = traffic_aware_duration("api-key", "origin", "destination", datetime(2026, 4, 28, 8, 0, tzinfo=TIMEZONE))

    assert duration == timedelta(seconds=1800)
    assert captured["json"]["travelMode"] == "DRIVE"
    assert captured["json"]["routingPreference"] == "TRAFFIC_AWARE"
    assert captured["json"]["origins"] == [{"waypoint": {"address": "origin"}}]
    assert captured["json"]["destinations"] == [{"waypoint": {"address": "destination"}}]
    assert captured["headers"]["X-Goog-Api-Key"] == "api-key"


def test_traffic_aware_duration_raises_when_no_route_exists(monkeypatch):
    monkeypatch.setattr(
        "homeaudio.vcal.departure_time.requests.post",
        lambda url, json, headers, timeout: _FakeResponse([{"originIndex": 0, "destinationIndex": 0, "condition": "NOT_FOUND"}]),
    )

    with pytest.raises(TravelTimeUnavailableError):
        traffic_aware_duration("api-key", "origin", "destination", datetime(2026, 4, 28, 8, 0, tzinfo=TIMEZONE))


def test_traffic_aware_duration_logs_response_body_on_http_error(monkeypatch, caplog):
    error_body = '{"error": {"message": "API key not valid"}}'
    monkeypatch.setattr(
        "homeaudio.vcal.departure_time.requests.post",
        lambda url, json, headers, timeout: _FakeResponse(None, status_code=400, text=error_body),
    )

    with pytest.raises(requests.HTTPError):
        with caplog.at_level("ERROR"):
            traffic_aware_duration("api-key", "origin", "destination", datetime(2026, 4, 28, 8, 0, tzinfo=TIMEZONE))

    assert error_body in caplog.text


# --- solve_car_departure_time -------------------------------------------------------------

def test_solve_car_departure_time_converges_and_applies_safety_factor():
    target_arrival = datetime(2026, 4, 28, 9, 0, tzinfo=TIMEZONE)
    now = datetime(2026, 4, 28, 7, 0, tzinfo=TIMEZONE)

    # Always reports a flat 20 minute duration regardless of departure time, so the very first
    # iteration already converges (next_guess == departure_guess after the second call).
    def fetch_duration(departure_time):
        return timedelta(minutes=20)

    result = solve_car_departure_time(
        target_arrival=target_arrival,
        cached_duration=timedelta(minutes=20),
        safety_factor=10,
        now=now,
        fetch_duration=fetch_duration,
    )

    assert result is not None
    car_departure_time, duration = result
    assert duration == timedelta(minutes=20)
    # padded_duration = 20 + 20*10/100 = 22 minutes
    assert car_departure_time == target_arrival - timedelta(minutes=22)


def test_solve_car_departure_time_warm_starts_from_cached_duration():
    target_arrival = datetime(2026, 4, 28, 9, 0, tzinfo=TIMEZONE)
    now = datetime(2026, 4, 28, 7, 0, tzinfo=TIMEZONE)
    queried_departure_times = []

    def fetch_duration(departure_time):
        queried_departure_times.append(departure_time)
        return timedelta(minutes=15)

    solve_car_departure_time(
        target_arrival=target_arrival,
        cached_duration=timedelta(minutes=15),
        safety_factor=0,
        now=now,
        fetch_duration=fetch_duration,
    )

    # First query should be seeded from target_arrival - cached_duration, not the 30 minute default.
    assert queried_departure_times[0] == target_arrival - timedelta(minutes=15)


def test_solve_car_departure_time_uses_default_guess_when_no_cached_duration():
    target_arrival = datetime(2026, 4, 28, 9, 0, tzinfo=TIMEZONE)
    now = datetime(2026, 4, 28, 7, 0, tzinfo=TIMEZONE)
    queried_departure_times = []

    def fetch_duration(departure_time):
        queried_departure_times.append(departure_time)
        return timedelta(minutes=30)

    solve_car_departure_time(
        target_arrival=target_arrival,
        cached_duration=None,
        safety_factor=0,
        now=now,
        fetch_duration=fetch_duration,
    )

    assert queried_departure_times[0] == target_arrival - DEFAULT_TRIP_DURATION_GUESS


def test_solve_car_departure_time_clamps_query_time_to_now_but_not_the_result():
    # Running late: the naive departure guess is already in the past.
    target_arrival = datetime(2026, 4, 28, 7, 10, tzinfo=TIMEZONE)
    now = datetime(2026, 4, 28, 7, 0, tzinfo=TIMEZONE)
    queried_departure_times = []

    def fetch_duration(departure_time):
        queried_departure_times.append(departure_time)
        return timedelta(minutes=30)  # naive guess: target_arrival - 30m, well before `now`

    result = solve_car_departure_time(
        target_arrival=target_arrival,
        cached_duration=timedelta(minutes=30),
        safety_factor=0,
        now=now,
        fetch_duration=fetch_duration,
    )

    assert all(query_time >= now for query_time in queried_departure_times)
    car_departure_time, _ = result
    assert car_departure_time == target_arrival - timedelta(minutes=30)  # kept in the past, not clamped


def test_solve_car_departure_time_stops_after_max_iterations_even_without_converging():
    target_arrival = datetime(2026, 4, 28, 9, 0, tzinfo=TIMEZONE)
    now = datetime(2026, 4, 28, 7, 0, tzinfo=TIMEZONE)
    call_count = {"n": 0}

    def fetch_duration(departure_time):
        # Oscillates so it never converges within CONVERGENCE_THRESHOLD.
        call_count["n"] += 1
        return timedelta(minutes=10) if call_count["n"] % 2 else timedelta(minutes=40)

    result = solve_car_departure_time(
        target_arrival=target_arrival,
        cached_duration=timedelta(minutes=25),  # differs from both oscillating values, so it never converges
        safety_factor=0,
        now=now,
        fetch_duration=fetch_duration,
    )

    assert result is not None
    assert call_count["n"] == MAX_ITERATIONS


def test_solve_car_departure_time_returns_none_when_every_call_fails():
    def fetch_duration(departure_time):
        raise RuntimeError("boom")

    result = solve_car_departure_time(
        target_arrival=datetime(2026, 4, 28, 9, 0, tzinfo=TIMEZONE),
        cached_duration=timedelta(minutes=20),
        safety_factor=0,
        now=datetime(2026, 4, 28, 7, 0, tzinfo=TIMEZONE),
        fetch_duration=fetch_duration,
    )

    assert result is None


def test_solve_car_departure_time_falls_back_to_last_successful_guess_on_later_failure():
    target_arrival = datetime(2026, 4, 28, 9, 0, tzinfo=TIMEZONE)
    now = datetime(2026, 4, 28, 7, 0, tzinfo=TIMEZONE)
    call_count = {"n": 0}

    def fetch_duration(departure_time):
        call_count["n"] += 1
        if call_count["n"] == 1:
            return timedelta(minutes=25)
        raise RuntimeError("boom")

    result = solve_car_departure_time(
        target_arrival=target_arrival,
        cached_duration=timedelta(minutes=30),  # differs enough from 25m that it won't converge on call 1
        safety_factor=0,
        now=now,
        fetch_duration=fetch_duration,
    )

    assert result == (target_arrival - timedelta(minutes=25), timedelta(minutes=25))


# --- TravelTimeCache ----------------------------------------------------------------------

def test_travel_time_cache_get_set_round_trip():
    cache = TravelTimeCache(cache_file_path="")
    entry = TravelTimeCacheEntry(
        car_departure_time=datetime(2026, 4, 28, 8, 0, tzinfo=TIMEZONE),
        duration_seconds=1200,
        computed_at=datetime(2026, 4, 28, 7, 0, tzinfo=TIMEZONE),
        event_start_time=datetime(2026, 4, 28, 9, 0, tzinfo=TIMEZONE),
        location="123 Fake St",
        parking_minutes=5,
        safety_factor=10,
    )

    assert cache.get("evt-1") is None
    cache.set("evt-1", entry)
    assert cache.get("evt-1") == entry


def test_travel_time_cache_save_and_load_round_trip(tmp_path):
    cache_file_path = str(tmp_path / "travel_time_cache.json")
    entry = TravelTimeCacheEntry(
        car_departure_time=datetime(2026, 4, 28, 8, 0, tzinfo=TIMEZONE),
        duration_seconds=1200,
        computed_at=datetime(2026, 4, 28, 7, 0, tzinfo=TIMEZONE),
        event_start_time=datetime(2026, 4, 28, 9, 0, tzinfo=TIMEZONE),
        location="123 Fake St",
        parking_minutes=5,
        safety_factor=10,
    )
    cache = TravelTimeCache(cache_file_path=cache_file_path)
    cache.set("evt-1", entry)
    cache.save()

    loaded = TravelTimeCache.load(cache_file_path)

    assert loaded.get("evt-1") == entry


def test_travel_time_cache_load_returns_empty_when_file_missing(tmp_path):
    cache = TravelTimeCache.load(str(tmp_path / "missing.json"))

    assert cache.entries == {}


def test_travel_time_cache_prune_keeps_entries_for_events_earlier_today():
    now = datetime(2026, 4, 28, 9, 0, tzinfo=TIMEZONE)
    cache = TravelTimeCache(cache_file_path="")
    earlier_today_entry = TravelTimeCacheEntry(
        car_departure_time=now - timedelta(hours=2),
        duration_seconds=600,
        computed_at=now - timedelta(hours=1),
        event_start_time=now - timedelta(minutes=1),
        location="Somewhere",
        parking_minutes=5,
        safety_factor=10,
    )
    future_entry = TravelTimeCacheEntry(
        car_departure_time=now + timedelta(hours=1),
        duration_seconds=600,
        computed_at=now,
        event_start_time=now + timedelta(hours=2),
        location="Somewhere else",
        parking_minutes=5,
        safety_factor=10,
    )
    cache.set("earlier_today", earlier_today_entry)
    cache.set("future", future_entry)

    cache.prune(now)

    assert cache.get("earlier_today") == earlier_today_entry
    assert cache.get("future") == future_entry


def test_travel_time_cache_prune_drops_entries_for_events_from_yesterday():
    now = datetime(2026, 4, 28, 9, 0, tzinfo=TIMEZONE)
    cache = TravelTimeCache(cache_file_path="")
    yesterday_entry = TravelTimeCacheEntry(
        car_departure_time=now - timedelta(days=1, hours=2),
        duration_seconds=600,
        computed_at=now - timedelta(days=1, hours=1),
        event_start_time=now - timedelta(days=1),
        location="Somewhere",
        parking_minutes=5,
        safety_factor=10,
    )
    cache.set("yesterday", yesterday_entry)

    cache.prune(now)

    assert cache.get("yesterday") is None


# --- car_departure_time_for_event ---------------------------------------------------------

def _located_event_today(now, **overrides):
    defaults = dict(
        owner="Beth",
        calendar_id="id",
        summary="Dentist",
        description="",
        location="123 Fake St",
        start_time=now + timedelta(hours=2),
        google_event_id="evt-1",
    )
    defaults.update(overrides)
    return Event(**defaults)


def test_car_departure_time_for_event_skips_events_with_no_location():
    now = datetime(2026, 4, 28, 7, 0, tzinfo=TIMEZONE)
    event = _located_event_today(now, location=None)
    cache = TravelTimeCache(cache_file_path="")

    result = car_departure_time_for_event(event, _settings(), cache, now)

    assert result is None
    assert cache.get("evt-1") is None


def test_car_departure_time_for_event_skips_events_not_starting_today():
    now = datetime(2026, 4, 28, 7, 0, tzinfo=TIMEZONE)
    event = _located_event_today(now, start_time=now + timedelta(days=1))
    cache = TravelTimeCache(cache_file_path="")

    result = car_departure_time_for_event(event, _settings(), cache, now)

    assert result is None
    assert cache.get("evt-1") is None


def test_car_departure_time_for_event_still_solves_when_start_time_has_passed_with_no_cache(monkeypatch):
    now = datetime(2026, 4, 28, 10, 0, tzinfo=TIMEZONE)
    event = _located_event_today(now, start_time=now - timedelta(hours=1))
    cache = TravelTimeCache(cache_file_path="")
    new_departure_time = now - timedelta(minutes=90)
    monkeypatch.setattr(
        "homeaudio.vcal.departure_time.solve_car_departure_time",
        lambda **kwargs: (new_departure_time, timedelta(minutes=10)),
    )

    result = car_departure_time_for_event(event, _settings(), cache, now)

    assert result == new_departure_time
    assert cache.get("evt-1").car_departure_time == new_departure_time


def test_car_departure_time_for_event_uses_stale_cache_entry_once_car_departure_time_has_passed(monkeypatch):
    now = datetime(2026, 4, 28, 10, 0, tzinfo=TIMEZONE)
    event = _located_event_today(now, start_time=now - timedelta(hours=1))
    cache = TravelTimeCache(cache_file_path="")
    cached_departure_time = now - timedelta(hours=2)
    cache.set("evt-1", TravelTimeCacheEntry(
        car_departure_time=cached_departure_time,
        duration_seconds=600,
        computed_at=now - timedelta(hours=3),  # well outside recompute_interval_minutes, but should still be used
        event_start_time=event.start_time,
        location=event.location,
        parking_minutes=5,
        safety_factor=10,
    ))
    monkeypatch.setattr(
        "homeaudio.vcal.departure_time.solve_car_departure_time",
        lambda **kwargs: pytest.fail("must not solve once the cached car_departure_time has already passed"),
    )

    result = car_departure_time_for_event(event, _settings(recompute_interval_minutes=20), cache, now)

    assert result == cached_departure_time


def test_car_departure_time_for_event_uses_stale_cache_entry_once_car_departure_time_has_passed_even_if_event_has_not_started(monkeypatch):
    now = datetime(2026, 4, 28, 10, 0, tzinfo=TIMEZONE)
    # The event itself hasn't started yet, but the computed car_departure_time already has -
    # the "time to leave" notification has already played, so there's no need to recompute.
    event = _located_event_today(now, start_time=now + timedelta(minutes=30))
    cache = TravelTimeCache(cache_file_path="")
    cached_departure_time = now - timedelta(minutes=5)
    cache.set("evt-1", TravelTimeCacheEntry(
        car_departure_time=cached_departure_time,
        duration_seconds=600,
        computed_at=now - timedelta(hours=3),
        event_start_time=event.start_time,
        location=event.location,
        parking_minutes=5,
        safety_factor=10,
    ))
    monkeypatch.setattr(
        "homeaudio.vcal.departure_time.solve_car_departure_time",
        lambda **kwargs: pytest.fail("must not solve once the cached car_departure_time has already passed"),
    )

    result = car_departure_time_for_event(event, _settings(recompute_interval_minutes=20), cache, now)

    assert result == cached_departure_time


def test_car_departure_time_for_event_recomputes_when_start_time_changes_after_cached_departure_time_passed(monkeypatch):
    now = datetime(2026, 4, 28, 10, 0, tzinfo=TIMEZONE)
    # The cached car_departure_time (for the event's old start_time) has already passed, but the
    # event's start_time has since been edited to later today - it must be treated as stale, not
    # short-circuited as "already played".
    event = _located_event_today(now, start_time=now + timedelta(hours=3))
    cache = TravelTimeCache(cache_file_path="")
    cache.set("evt-1", TravelTimeCacheEntry(
        car_departure_time=now - timedelta(minutes=5),
        duration_seconds=600,
        computed_at=now - timedelta(hours=3),
        event_start_time=now - timedelta(minutes=30),  # the old, no-longer-current start_time
        location=event.location,
        parking_minutes=5,
        safety_factor=10,
    ))
    new_departure_time = now + timedelta(hours=2)
    monkeypatch.setattr(
        "homeaudio.vcal.departure_time.solve_car_departure_time",
        lambda **kwargs: (new_departure_time, timedelta(minutes=10)),
    )

    result = car_departure_time_for_event(event, _settings(recompute_interval_minutes=20), cache, now)

    assert result == new_departure_time


@pytest.mark.parametrize("description", ["#travel", "#travel20"])
def test_car_departure_time_for_event_skips_events_with_a_travel_tag(monkeypatch, description):
    now = datetime(2026, 4, 28, 7, 0, tzinfo=TIMEZONE)
    event = _located_event_today(now, description=description)
    cache = TravelTimeCache(cache_file_path="")
    monkeypatch.setattr(
        "homeaudio.vcal.departure_time.solve_car_departure_time",
        lambda **kwargs: pytest.fail("must not solve for an event with a #travel/#travel<N> tag"),
    )

    result = car_departure_time_for_event(event, _settings(), cache, now)

    assert result is None
    assert cache.get("evt-1") is None


def test_car_departure_time_for_event_reuses_a_fresh_cache_entry(monkeypatch):
    now = datetime(2026, 4, 28, 7, 0, tzinfo=TIMEZONE)
    event = _located_event_today(now)
    cache = TravelTimeCache(cache_file_path="")
    cached_departure_time = now + timedelta(hours=1)
    cache.set("evt-1", TravelTimeCacheEntry(
        car_departure_time=cached_departure_time,
        duration_seconds=600,
        computed_at=now - timedelta(minutes=5),
        event_start_time=event.start_time,
        location=event.location,
        parking_minutes=5,
        safety_factor=10,
    ))
    monkeypatch.setattr(
        "homeaudio.vcal.departure_time.solve_car_departure_time",
        lambda **kwargs: pytest.fail("must not recompute a fresh cache entry"),
    )

    result = car_departure_time_for_event(event, _settings(recompute_interval_minutes=20), cache, now)

    assert result == cached_departure_time


def test_car_departure_time_for_event_recomputes_after_the_interval_elapses(monkeypatch):
    now = datetime(2026, 4, 28, 7, 0, tzinfo=TIMEZONE)
    event = _located_event_today(now)
    cache = TravelTimeCache(cache_file_path="")
    cache.set("evt-1", TravelTimeCacheEntry(
        car_departure_time=now + timedelta(hours=1),
        duration_seconds=600,
        computed_at=now - timedelta(minutes=21),
        event_start_time=event.start_time,
        location=event.location,
        parking_minutes=5,
        safety_factor=10,
    ))
    new_departure_time = now + timedelta(hours=1, minutes=30)
    monkeypatch.setattr(
        "homeaudio.vcal.departure_time.solve_car_departure_time",
        lambda **kwargs: (new_departure_time, timedelta(minutes=10)),
    )

    result = car_departure_time_for_event(event, _settings(recompute_interval_minutes=20), cache, now)

    assert result == new_departure_time
    assert cache.get("evt-1").car_departure_time == new_departure_time


@pytest.mark.parametrize("changed_field, changed_value", [
    ("start_time_shift", timedelta(minutes=30)),
    ("location", "A different address"),
])
def test_car_departure_time_for_event_forces_recompute_when_event_details_change(monkeypatch, changed_field, changed_value):
    now = datetime(2026, 4, 28, 7, 0, tzinfo=TIMEZONE)
    event = _located_event_today(now)
    cached_start_time = event.start_time if changed_field != "start_time_shift" else event.start_time - changed_value
    cached_location = event.location if changed_field != "location" else changed_value

    cache = TravelTimeCache(cache_file_path="")
    cache.set("evt-1", TravelTimeCacheEntry(
        car_departure_time=now + timedelta(hours=1),
        duration_seconds=600,
        computed_at=now,  # otherwise fresh - only the changed field should force a recompute
        event_start_time=cached_start_time,
        location=cached_location,
        parking_minutes=5,
        safety_factor=10,
    ))
    new_departure_time = now + timedelta(hours=1)
    monkeypatch.setattr(
        "homeaudio.vcal.departure_time.solve_car_departure_time",
        lambda **kwargs: (new_departure_time, timedelta(minutes=10)),
    )

    result = car_departure_time_for_event(event, _settings(), cache, now)

    assert result == new_departure_time


def test_car_departure_time_for_event_forces_recompute_when_settings_change(monkeypatch):
    now = datetime(2026, 4, 28, 7, 0, tzinfo=TIMEZONE)
    event = _located_event_today(now)
    cache = TravelTimeCache(cache_file_path="")
    cache.set("evt-1", TravelTimeCacheEntry(
        car_departure_time=now + timedelta(hours=1),
        duration_seconds=600,
        computed_at=now,
        event_start_time=event.start_time,
        location=event.location,
        parking_minutes=5,
        safety_factor=999,  # doesn't match settings below
    ))
    new_departure_time = now + timedelta(hours=1)
    monkeypatch.setattr(
        "homeaudio.vcal.departure_time.solve_car_departure_time",
        lambda **kwargs: (new_departure_time, timedelta(minutes=10)),
    )

    result = car_departure_time_for_event(event, _settings(safety_factor=10), cache, now)

    assert result == new_departure_time


def test_car_departure_time_for_event_keeps_previous_estimate_when_solve_fails(monkeypatch):
    now = datetime(2026, 4, 28, 7, 0, tzinfo=TIMEZONE)
    event = _located_event_today(now)
    cache = TravelTimeCache(cache_file_path="")
    previous_departure_time = now + timedelta(minutes=45)
    cache.set("evt-1", TravelTimeCacheEntry(
        car_departure_time=previous_departure_time,
        duration_seconds=600,
        computed_at=now - timedelta(minutes=21),
        event_start_time=event.start_time,
        location=event.location,
        parking_minutes=5,
        safety_factor=10,
    ))
    monkeypatch.setattr("homeaudio.vcal.departure_time.solve_car_departure_time", lambda **kwargs: None)

    result = car_departure_time_for_event(event, _settings(recompute_interval_minutes=20), cache, now)

    assert result == previous_departure_time


def test_car_departure_time_for_event_returns_none_when_solve_fails_with_no_prior_cache(monkeypatch):
    now = datetime(2026, 4, 28, 7, 0, tzinfo=TIMEZONE)
    event = _located_event_today(now)
    cache = TravelTimeCache(cache_file_path="")
    monkeypatch.setattr("homeaudio.vcal.departure_time.solve_car_departure_time", lambda **kwargs: None)

    result = car_departure_time_for_event(event, _settings(), cache, now)

    assert result is None
