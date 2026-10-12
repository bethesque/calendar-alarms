from datetime import date

import homeaudio.vcal.cal.google_calendar as google_calendar
from homeaudio.audio.settings import CalendarSetting
from homeaudio.vcal.cal.google_calendar import CalendarDay, CalendarSource, Event, WeatherForecast, add_events_to_calendars, is_school_holiday, load_calendar_days, load_google_creds

DEFAULT_HOLIDAY_KEYWORDS = ["no school", "school holidays"]


def test_load_google_creds_returns_none_when_no_token_info():
    assert load_google_creds(None) is None


def test_load_google_creds_loads_credentials_from_token_info():
    token_info = {
        "token": "access-token",
        "refresh_token": "refresh-token",
        "client_id": "client-id",
        "client_secret": "client-secret",
        "expiry": "2099-01-01T00:00:00Z",
    }

    creds = load_google_creds(token_info)

    assert creds.token == "access-token"
    assert creds.refresh_token == "refresh-token"


def test_is_school_holiday_true_when_holiday_keyword_matches_case_insensitively():
    events = [Event(owner="cal", summary="no SCHOOL today", description="", calendar_id="id")]

    assert is_school_holiday(events, DEFAULT_HOLIDAY_KEYWORDS) is True


def test_is_school_holiday_true_for_configured_keyword():
    events = [Event(owner="cal", summary="Public Holiday", description="", calendar_id="id")]

    assert is_school_holiday(events, ["public holiday"]) is True


def test_is_school_holiday_false_when_no_keyword_matches():
    events = [Event(owner="cal", summary="School Assembly", description="", calendar_id="id")]

    assert is_school_holiday(events, DEFAULT_HOLIDAY_KEYWORDS) is False


def test_is_school_holiday_true_when_event_is_from_a_holiday_calendar():
    events = [Event(owner="cal", summary="Labour Day", description="", calendar_id="holidays-id")]

    assert is_school_holiday(events, DEFAULT_HOLIDAY_KEYWORDS, ["holidays-id"]) is True


def test_is_school_holiday_false_when_event_is_not_from_a_holiday_calendar():
    events = [Event(owner="cal", summary="Labour Day", description="", calendar_id="other-id")]

    assert is_school_holiday(events, DEFAULT_HOLIDAY_KEYWORDS, ["holidays-id"]) is False


def test_fetch_data_sets_holiday_on_days_with_a_holiday_calendar_event(monkeypatch):
    holiday_event = Event(owner="cal", summary="Labour Day", description="", calendar_id="holidays-id")
    days = [
        CalendarDay(date=date(2026, 4, 6), whole_day_events=[holiday_event]),
        CalendarDay(date=date(2026, 4, 7)),
    ]
    monkeypatch.setattr(google_calendar, "get_calendar_days", lambda creds, calendars: days)

    calendar_days = CalendarSource(cache_file_path="").fetch_data([CalendarSetting(id="holidays-id", name="Public Holidays", holiday=True)], DEFAULT_HOLIDAY_KEYWORDS)

    assert [day.holiday for day in calendar_days] == [True, False]


def test_fetch_data_sets_holiday_on_days_with_a_holiday_keyword_event(monkeypatch):
    holiday_event = Event(owner="cal", summary="School holidays", description="", calendar_id="id")
    days = [
        CalendarDay(date=date(2026, 4, 6), whole_day_events=[holiday_event]),
        CalendarDay(date=date(2026, 4, 7)),
    ]
    monkeypatch.setattr(google_calendar, "get_calendar_days", lambda creds, calendars: days)

    calendar_days = CalendarSource(cache_file_path="").fetch_data([], DEFAULT_HOLIDAY_KEYWORDS)

    assert [day.holiday for day in calendar_days] == [True, False]


def test_holiday_round_trips_through_the_calendar_file(tmp_path):
    cache_file_path = str(tmp_path / "calendar.json")
    source = CalendarSource(cache_file_path=cache_file_path)
    source.calendar_days = [CalendarDay(date=date(2026, 4, 6), holiday=True), CalendarDay(date=date(2026, 4, 7))]
    source.save_data_to_file()

    calendar_days = CalendarSource(cache_file_path=cache_file_path).load_data_from_file()

    assert [day.holiday for day in calendar_days] == [True, False]


def test_holiday_defaults_to_false_for_calendar_files_written_without_it():
    calendar_days = CalendarSource(cache_file_path="").load_data_from_any(
        [{"date": "2026-04-06", "whole_day_events": [], "timed_events": []}]
    )

    assert calendar_days[0].holiday is False


def test_add_events_to_calendars_puts_weather_forecasts_in_weather_forecasts():
    day = CalendarDay(date=date(2026, 4, 6))
    events = [
        {"summary": "Min 10 Max 20", "start": {"date": "2026-04-06"}, "end": {"date": "2026-04-07"}},
        {"summary": "Pupil free day", "start": {"date": "2026-04-06"}, "end": {"date": "2026-04-07"}},
    ]

    add_events_to_calendars(events, "id", "cal", [day], 1)

    assert [event.summary for event in day.weather_forecasts] == ["Min 10 Max 20"]
    assert isinstance(day.weather_forecasts[0], WeatherForecast)
    assert [event.summary for event in day.whole_day_events] == ["Pupil free day"]


def test_weather_forecasts_round_trip_through_the_calendar_file(tmp_path):
    cache_file_path = str(tmp_path / "calendar.json")
    source = CalendarSource(cache_file_path=cache_file_path)
    weather = WeatherForecast(owner="cal", summary="Min 10 Max 20", description="", calendar_id="id")
    source.calendar_days = [CalendarDay(date=date(2026, 4, 6), weather_forecasts=[weather])]
    source.save_data_to_file()

    calendar_days = CalendarSource(cache_file_path=cache_file_path).load_data_from_file()

    assert calendar_days[0].weather_forecasts == [weather]
    assert calendar_days[0].whole_day_events == []


def test_load_calendar_days_returns_empty_list_when_the_calendar_file_is_missing(monkeypatch, tmp_path):
    missing_file = str(tmp_path / "missing.json")
    monkeypatch.setattr(google_calendar, "CalendarSource", lambda: CalendarSource(cache_file_path=missing_file))

    assert load_calendar_days() == []


def test_load_calendar_days_returns_empty_list_when_the_calendar_file_is_corrupt(monkeypatch, tmp_path):
    corrupt_file = tmp_path / "calendar.json"
    corrupt_file.write_text("{not json")
    monkeypatch.setattr(google_calendar, "CalendarSource", lambda: CalendarSource(cache_file_path=str(corrupt_file)))

    assert load_calendar_days() == []

