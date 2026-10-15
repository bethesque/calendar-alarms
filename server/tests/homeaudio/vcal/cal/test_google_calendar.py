from datetime import date, datetime, timedelta

import pytest

import homeaudio.vcal.cal.google_calendar as google_calendar
from homeaudio.audio.settings import CalendarSetting
from homeaudio.vcal.cal.google_calendar import CalendarDay, CalendarDayList, CalendarSource, WholeDayEvent, GoogleCalendar, MissingCalendarDataException, WeatherForecast, add_events_to_calendars, copy_min_temperature_from_existing_day, fetch_calendar_days_from_google, is_school_holiday, load_calendar_days, load_data_from_any, load_google_creds, Event

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
    events = [WholeDayEvent(owner="cal", summary="no SCHOOL today", description="", calendar_id="id")]

    assert is_school_holiday(events, DEFAULT_HOLIDAY_KEYWORDS) is True


def test_is_school_holiday_true_for_configured_keyword():
    events = [WholeDayEvent(owner="cal", summary="Public Holiday", description="", calendar_id="id")]

    assert is_school_holiday(events, ["public holiday"]) is True


def test_is_school_holiday_false_when_no_keyword_matches():
    events = [WholeDayEvent(owner="cal", summary="School Assembly", description="", calendar_id="id")]

    assert is_school_holiday(events, DEFAULT_HOLIDAY_KEYWORDS) is False


def test_is_school_holiday_true_when_event_is_from_a_holiday_calendar():
    events = [WholeDayEvent(owner="cal", summary="Labour Day", description="", calendar_id="holidays-id")]

    assert is_school_holiday(events, DEFAULT_HOLIDAY_KEYWORDS, ["holidays-id"]) is True


def test_is_school_holiday_false_when_event_is_not_from_a_holiday_calendar():
    events = [WholeDayEvent(owner="cal", summary="Labour Day", description="", calendar_id="other-id")]

    assert is_school_holiday(events, DEFAULT_HOLIDAY_KEYWORDS, ["holidays-id"]) is False


def test_fetch_data_sets_holiday_on_days_with_a_holiday_calendar_event(monkeypatch, tmp_path):
    holiday_event = WholeDayEvent(owner="cal", summary="Labour Day", description="", calendar_id="holidays-id")
    days = CalendarDayList([
        CalendarDay(date=date(2026, 4, 6), whole_day_events=[holiday_event]),
        CalendarDay(date=date(2026, 4, 7)),
    ])
    monkeypatch.setattr(google_calendar, "fetch_calendar_days_from_google", lambda creds, calendars: days)

    calendar_days = CalendarSource(cache_file_path=str(tmp_path / "calendar.json")).fetch_data([CalendarSetting(id="holidays-id", name="Public Holidays", holiday=True)], DEFAULT_HOLIDAY_KEYWORDS)

    assert [day.holiday for day in calendar_days] == [True, False]


def test_fetch_data_sets_holiday_on_days_with_a_holiday_keyword_event(monkeypatch, tmp_path):
    holiday_event = WholeDayEvent(owner="cal", summary="School holidays", description="", calendar_id="id")
    days = CalendarDayList([
        CalendarDay(date=date(2026, 4, 6), whole_day_events=[holiday_event]),
        CalendarDay(date=date(2026, 4, 7)),
    ])
    monkeypatch.setattr(google_calendar, "fetch_calendar_days_from_google", lambda creds, calendars: days)

    calendar_days = CalendarSource(cache_file_path=str(tmp_path / "calendar.json")).fetch_data([], DEFAULT_HOLIDAY_KEYWORDS)

    assert [day.holiday for day in calendar_days] == [True, False]


def test_holiday_round_trips_through_the_calendar_file(tmp_path):
    cache_file_path = str(tmp_path / "calendar.json")
    source = CalendarSource(cache_file_path=cache_file_path)
    source.calendar_days = CalendarDayList([CalendarDay(date=date(2026, 4, 6), holiday=True), CalendarDay(date=date(2026, 4, 7))])
    source.save_data_to_file()

    calendar_days = CalendarSource(cache_file_path=cache_file_path).load_data_from_file()

    assert [day.holiday for day in calendar_days] == [True, False]


def test_holiday_defaults_to_false_for_calendar_files_written_without_it():
    calendar_days = CalendarSource(cache_file_path="").load_data_from_any(
        [{"date": "2026-04-06", "whole_day_events": [], "timed_events": []}]
    )

    assert calendar_days[0].holiday is False


def test_add_events_to_calendars_puts_events_from_a_weather_calendar_in_weather_forecasts():
    day = CalendarDay(date=date(2026, 4, 6))
    events = [{"summary": "Min 10 Max 20", "start": {"date": "2026-04-06"}, "end": {"date": "2026-04-07"}}]

    add_events_to_calendars(events, "weather-id", "Weather", [day], 1, weather=True)

    assert [event.summary for event in day.weather_forecasts] == ["Min 10 Max 20"]
    assert isinstance(day.weather_forecasts[0], WeatherForecast)
    assert day.whole_day_events == []


def test_add_events_to_calendars_puts_min_max_events_from_a_non_weather_calendar_in_whole_day_events():
    day = CalendarDay(date=date(2026, 4, 6))
    events = [{"summary": "Min 10 Max 20", "start": {"date": "2026-04-06"}, "end": {"date": "2026-04-07"}}]

    add_events_to_calendars(events, "id", "cal", [day], 1)

    assert [event.summary for event in day.whole_day_events] == ["Min 10 Max 20"]
    assert not isinstance(day.whole_day_events[0], WeatherForecast)
    assert day.weather_forecasts == []


def test_fetch_calendar_days_from_google_uses_the_calendar_weather_setting(monkeypatch):
    today = date.today().isoformat()
    tomorrow = (date.today() + timedelta(days=1)).isoformat()
    events_by_calendar = {
        "weather-id": [{"summary": "Sunny", "start": {"date": today}, "end": {"date": tomorrow}}],
        "family-id": [{"summary": "Pupil free day", "start": {"date": today}, "end": {"date": tomorrow}}],
    }
    monkeypatch.setattr(google_calendar, "list_google_calendars", lambda creds: [GoogleCalendar("weather-id", "Weather"), GoogleCalendar("family-id", "Family")])
    monkeypatch.setattr(google_calendar, "list_google_events", lambda creds, calendar_id, min, max: events_by_calendar[calendar_id])
    calendars = [CalendarSetting(id="weather-id", name="Weather", weather=True), CalendarSetting(id="family-id", name="Family")]

    calendar_days = fetch_calendar_days_from_google(None, calendars)

    assert [event.summary for event in calendar_days[0].weather_forecasts] == ["Sunny"]
    assert [event.summary for event in calendar_days[0].whole_day_events] == ["Pupil free day"]


def test_weather_forecasts_round_trip_through_the_calendar_file(tmp_path):
    cache_file_path = str(tmp_path / "calendar.json")
    source = CalendarSource(cache_file_path=cache_file_path)
    weather = WeatherForecast(owner="cal", summary="Min 10 Max 20", description="", calendar_id="id")
    source.calendar_days = CalendarDayList([CalendarDay(date=date(2026, 4, 6), weather_forecasts=[weather])])
    source.save_data_to_file()

    calendar_days = CalendarSource(cache_file_path=cache_file_path).load_data_from_file()

    assert calendar_days[0].weather_forecasts == [weather]
    assert calendar_days[0].whole_day_events == []


def test_weather_forecast_min_temperature():
    assert WeatherForecast(owner="cal", summary="Min 11, Max 25", description="", calendar_id="id").min_temperature() == 11


def test_weather_forecast_min_temperature_when_negative():
    assert WeatherForecast(owner="cal", summary="Min -2, Max 9", description="", calendar_id="id").min_temperature() == -2


def test_weather_forecast_min_temperature_returns_none_when_missing():
    assert WeatherForecast(owner="cal", summary="Max 25", description="", calendar_id="id").min_temperature() is None


def test_weather_forecast_add_min_temperature():
    forecast = WeatherForecast(owner="cal", summary="Max 25", description="", calendar_id="id")

    forecast.add_min_temperature(11)

    assert forecast.summary == "Min 11, Max 25"
    assert forecast.min_temperature() == 11


def test_calendar_day_list_get_calendar_day_for_date():
    days = CalendarDayList([CalendarDay(date=date(2026, 4, 6)), CalendarDay(date=date(2026, 4, 7))])

    assert days.get_calendar_day_for_date(datetime(2026, 4, 7, 9, 30)) is days[1]


def test_calendar_day_list_get_calendar_day_for_date_raises_when_date_is_missing():
    days = CalendarDayList([CalendarDay(date=date(2026, 4, 6))])

    with pytest.raises(MissingCalendarDataException):
        days.get_calendar_day_for_date(datetime(2026, 4, 7, 9, 30))


def _weather_forecast(summary):
    return WeatherForecast(owner="cal", summary=summary, description="", calendar_id="id")


def test_copy_min_temperature_from_existing_day_adds_min_temperature_that_has_dropped_out_of_the_forecast():
    existing_days = CalendarDayList([CalendarDay(date=date(2026, 4, 6), weather_forecasts=[_weather_forecast("Min 11, Max 25")])])
    day = CalendarDay(date=date(2026, 4, 6), weather_forecasts=[_weather_forecast("Max 25")])

    copy_min_temperature_from_existing_day(existing_days, day)

    assert day.weather_forecasts[0].summary == "Min 11, Max 25"


def test_copy_min_temperature_from_existing_day_uses_the_first_existing_forecast_with_a_min_temperature():
    existing_forecasts = [_weather_forecast("Sunny"), _weather_forecast("Min 11, Max 25"), _weather_forecast("Min 9, Max 20")]
    existing_days = CalendarDayList([CalendarDay(date=date(2026, 4, 6), weather_forecasts=existing_forecasts)])
    day = CalendarDay(date=date(2026, 4, 6), weather_forecasts=[_weather_forecast("Max 25")])

    copy_min_temperature_from_existing_day(existing_days, day)

    assert day.weather_forecasts[0].summary == "Min 11, Max 25"


def test_copy_min_temperature_from_existing_day_adds_min_temperature_to_each_forecast_without_one():
    existing_days = CalendarDayList([CalendarDay(date=date(2026, 4, 6), weather_forecasts=[_weather_forecast("Min 11, Max 25")])])
    day = CalendarDay(date=date(2026, 4, 6), weather_forecasts=[_weather_forecast("Max 25"), _weather_forecast("Min 12, Max 24")])

    copy_min_temperature_from_existing_day(existing_days, day)

    assert [forecast.summary for forecast in day.weather_forecasts] == ["Min 11, Max 25", "Min 12, Max 24"]


def test_copy_min_temperature_from_existing_day_keeps_a_min_temperature_of_zero():
    existing_days = CalendarDayList([CalendarDay(date=date(2026, 4, 6), weather_forecasts=[_weather_forecast("Min 11, Max 25")])])
    day = CalendarDay(date=date(2026, 4, 6), weather_forecasts=[_weather_forecast("Min 0, Max 12")])

    copy_min_temperature_from_existing_day(existing_days, day)

    assert day.weather_forecasts[0].summary == "Min 0, Max 12"


def test_copy_min_temperature_from_existing_day_copies_a_min_temperature_of_zero():
    existing_days = CalendarDayList([CalendarDay(date=date(2026, 4, 6), weather_forecasts=[_weather_forecast("Min 0, Max 12")])])
    day = CalendarDay(date=date(2026, 4, 6), weather_forecasts=[_weather_forecast("Max 12")])

    copy_min_temperature_from_existing_day(existing_days, day)

    assert day.weather_forecasts[0].summary == "Min 0, Max 12"


def test_copy_min_temperature_from_existing_day_does_nothing_when_existing_forecasts_have_no_min_temperature():
    existing_days = CalendarDayList([CalendarDay(date=date(2026, 4, 6), weather_forecasts=[_weather_forecast("Max 25")])])
    day = CalendarDay(date=date(2026, 4, 6), weather_forecasts=[_weather_forecast("Max 24")])

    copy_min_temperature_from_existing_day(existing_days, day)

    assert day.weather_forecasts[0].summary == "Max 24"


def test_copy_min_temperature_from_existing_day_does_nothing_when_existing_day_has_no_forecasts():
    existing_days = CalendarDayList([CalendarDay(date=date(2026, 4, 6))])
    day = CalendarDay(date=date(2026, 4, 6), weather_forecasts=[_weather_forecast("Max 24")])

    copy_min_temperature_from_existing_day(existing_days, day)

    assert day.weather_forecasts[0].summary == "Max 24"


def test_copy_min_temperature_from_existing_day_does_nothing_when_there_is_no_existing_day_for_the_date():
    existing_days = CalendarDayList([CalendarDay(date=date(2026, 4, 5), weather_forecasts=[_weather_forecast("Min 11, Max 25")])])
    day = CalendarDay(date=date(2026, 4, 6), weather_forecasts=[_weather_forecast("Max 24")])

    copy_min_temperature_from_existing_day(existing_days, day)

    assert day.weather_forecasts[0].summary == "Max 24"


def _save_existing_weather_forecast(cache_file_path, day_date, summary):
    weather = WeatherForecast(owner="cal", summary=summary, description="", calendar_id="id")
    CalendarSource(cache_file_path=cache_file_path, calendar_days=CalendarDayList([CalendarDay(date=day_date, weather_forecasts=[weather])])).save_data_to_file()


def _fetch_weather_forecast(monkeypatch, cache_file_path, day_date, summary):
    weather = WeatherForecast(owner="cal", summary=summary, description="", calendar_id="id")
    days = CalendarDayList([CalendarDay(date=day_date, weather_forecasts=[weather])])
    monkeypatch.setattr(google_calendar, "fetch_calendar_days_from_google", lambda creds, calendars: days)
    return CalendarSource(cache_file_path=cache_file_path).fetch_data([], DEFAULT_HOLIDAY_KEYWORDS)[0].weather_forecasts[0]


def test_fetch_data_copies_min_temperature_from_existing_day_when_forecast_has_none(monkeypatch, tmp_path):
    cache_file_path = str(tmp_path / "calendar.json")
    _save_existing_weather_forecast(cache_file_path, date(2026, 4, 6), "Min 11, Max 25")

    forecast = _fetch_weather_forecast(monkeypatch, cache_file_path, date(2026, 4, 6), "Max 24")

    assert forecast.summary == "Min 11, Max 24"


def test_fetch_data_keeps_min_temperature_already_in_forecast(monkeypatch, tmp_path):
    cache_file_path = str(tmp_path / "calendar.json")
    _save_existing_weather_forecast(cache_file_path, date(2026, 4, 6), "Min 11, Max 25")

    forecast = _fetch_weather_forecast(monkeypatch, cache_file_path, date(2026, 4, 6), "Min 12, Max 24")

    assert forecast.summary == "Min 12, Max 24"


def test_fetch_data_does_not_add_min_temperature_when_existing_forecast_has_none(monkeypatch, tmp_path):
    cache_file_path = str(tmp_path / "calendar.json")
    _save_existing_weather_forecast(cache_file_path, date(2026, 4, 6), "Max 25")

    forecast = _fetch_weather_forecast(monkeypatch, cache_file_path, date(2026, 4, 6), "Max 24")

    assert forecast.summary == "Max 24"


def test_fetch_data_does_not_add_min_temperature_when_existing_data_has_no_matching_day(monkeypatch, tmp_path):
    cache_file_path = str(tmp_path / "calendar.json")
    _save_existing_weather_forecast(cache_file_path, date(2026, 4, 5), "Min 11, Max 25")

    forecast = _fetch_weather_forecast(monkeypatch, cache_file_path, date(2026, 4, 6), "Max 24")

    assert forecast.summary == "Max 24"


def test_fetch_data_does_not_add_min_temperature_when_there_is_no_existing_calendar_file(monkeypatch, tmp_path):
    forecast = _fetch_weather_forecast(monkeypatch, str(tmp_path / "calendar.json"), date(2026, 4, 6), "Max 24")

    assert forecast.summary == "Max 24"


def test_load_calendar_days_returns_empty_list_when_the_calendar_file_is_missing(monkeypatch, tmp_path):
    missing_file = str(tmp_path / "missing.json")
    monkeypatch.setattr(google_calendar, "CalendarSource", lambda: CalendarSource(cache_file_path=missing_file))

    assert load_calendar_days() == []


def test_load_calendar_days_returns_empty_list_when_the_calendar_file_is_corrupt(monkeypatch, tmp_path):
    corrupt_file = tmp_path / "calendar.json"
    corrupt_file.write_text("{not json")
    monkeypatch.setattr(google_calendar, "CalendarSource", lambda: CalendarSource(cache_file_path=str(corrupt_file)))

    assert load_calendar_days() == []



def test_load_data_from_any_loads_whole_day_events_as_whole_day_events_and_timed_events_as_events():
    event_fields = {"owner": "Beth", "calendar_id": "id", "summary": "Dentist", "description": ""}
    days = [{
        "date": "2026-04-28",
        "whole_day_events": [{**event_fields, "start_time": None, "end_time": None}],
        "timed_events": [{**event_fields, "start_time": "2026-04-28T12:30:00+10:00", "end_time": "2026-04-28T13:30:00+10:00"}],
    }]

    calendar_days = load_data_from_any(days)

    assert type(calendar_days[0].whole_day_events[0]) is WholeDayEvent
    assert type(calendar_days[0].timed_events[0]) is Event
    assert calendar_days[0].timed_events[0].start_time == datetime.fromisoformat("2026-04-28T12:30:00+10:00")
