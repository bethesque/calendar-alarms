import sys
from datetime import datetime, time as time_of_day
from pathlib import Path
from types import SimpleNamespace

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

import homeaudio.vcal.school_announcements.core as school_announcements_core
from homeaudio.vcal.school_announcements.core import (
    build_text,
    build_audio_file,
    is_school_holiday,
    get_school_events,
    get_weather_forecast,
    _seconds_until,
    play_school_announcements,
)
from homeaudio.vcal.cal.google_calendar import Event, WeatherForecast
from homeaudio.vcal.notifications import OUTPUT_AUDIO_DIRECTORY, PRE_ANNOUNCEMENT_BELL, POST_ANNOUNCEMENT_SILENCE

DEFAULT_HOLIDAY_KEYWORDS = ["no school", "school holidays"]
DEFAULT_SCHOOL_EVENT_KEYWORDS = ["school"]


def test_build_text_with_no_school_events():
    assert build_text([]) == ["It's time to leave for school."]


def test_build_text_lists_school_events():
    school_events = [
        Event(owner="cal", summary="SCHOOL Assembly", description="", calendar_id="id"),
    ]

    assert build_text(school_events) == [
        "It's time to leave for school.",
        "Today's school events are:",
        "SCHOOL Assembly.",
        "Have a nice day.",
    ]


def test_build_text_preserves_event_order_for_multiple_events():
    school_events = [
        Event(owner="cal", summary="School drop off", description="", calendar_id="id"),
        Event(owner="cal", summary="School excursion", description="", calendar_id="id"),
    ]

    assert build_text(school_events) == [
        "It's time to leave for school.",
        "Today's school events are:",
        "School drop off.",
        "School excursion.",
        "Have a nice day.",
    ]


def test_build_text_adds_umbrella_reminder_when_forecast_mentions_rain():
    weather_forecast = WeatherForecast(owner="cal", summary="Rain clearing later", description="", calendar_id="id")

    assert build_text([], weather_forecast) == [
        "It's time to leave for school.",
        "You may wish to pack an umbrella as there is rain forecast.",
    ]


def test_build_text_matches_rain_case_insensitively():
    weather_forecast = WeatherForecast(owner="cal", summary="Possible RAIN", description="", calendar_id="id")

    assert "You may wish to pack an umbrella as there is rain forecast." in build_text([], weather_forecast)


def test_build_text_adds_umbrella_reminder_when_forecast_mentions_showers():
    weather_forecast = WeatherForecast(owner="cal", summary="Scattered showers", description="", calendar_id="id")

    assert "You may wish to pack an umbrella as there is rain forecast." in build_text([], weather_forecast)


def test_build_text_omits_umbrella_reminder_when_forecast_has_no_rain():
    weather_forecast = WeatherForecast(owner="cal", summary="Sunny", description="", calendar_id="id")

    assert build_text([], weather_forecast) == ["It's time to leave for school."]


def test_build_text_omits_umbrella_reminder_when_no_forecast():
    assert build_text([], None) == ["It's time to leave for school."]


def test_build_text_puts_umbrella_reminder_before_school_events():
    school_events = [Event(owner="cal", summary="School excursion", description="", calendar_id="id")]
    weather_forecast = WeatherForecast(owner="cal", summary="Heavy rain", description="", calendar_id="id")

    assert build_text(school_events, weather_forecast) == [
        "It's time to leave for school.",
        "You may wish to pack an umbrella as there is rain forecast.",
        "Today's school events are:",
        "School excursion.",
        "Have a nice day.",
    ]


def test_get_weather_forecast_returns_the_weather_forecast_event():
    weather_forecast = WeatherForecast(owner="cal", summary="Min 10 Max 20", description="", calendar_id="id")
    events = [Event(owner="cal", summary="Dentist", description="", calendar_id="id"), weather_forecast]

    assert get_weather_forecast(events) is weather_forecast


def test_get_weather_forecast_returns_none_when_absent():
    events = [Event(owner="cal", summary="Dentist", description="", calendar_id="id")]

    assert get_weather_forecast(events) is None


def test_get_school_events_matches_summary_case_insensitively():
    events = [
        Event(owner="cal", summary="SCHOOL Assembly", description="", calendar_id="id"),
        Event(owner="cal", summary="Dentist", description="", calendar_id="id"),
    ]

    assert get_school_events(events, DEFAULT_SCHOOL_EVENT_KEYWORDS) == [events[0]]


def test_get_school_events_matches_description():
    events = [
        Event(owner="cal", summary="Pickup", description="Reminder: School photo day", calendar_id="id"),
        Event(owner="cal", summary="Dentist", description="", calendar_id="id"),
    ]

    assert get_school_events(events, DEFAULT_SCHOOL_EVENT_KEYWORDS) == [events[0]]


def test_get_school_events_with_no_matches():
    events = [
        Event(owner="cal", summary="Dentist", description="", calendar_id="id"),
        Event(owner="cal", summary="Meeting", description="", calendar_id="id"),
    ]

    assert get_school_events(events, DEFAULT_SCHOOL_EVENT_KEYWORDS) == []


def test_build_audio_file_joins_bell_and_speech_files(monkeypatch):
    speech_files_by_sentence = {
        "Sentence one.": "speech1.mp3",
        "Sentence two.": "speech2.mp3",
    }
    monkeypatch.setattr(
        "homeaudio.vcal.school_announcements.core.text_to_voice_file",
        lambda sentence, tld: speech_files_by_sentence[sentence],
    )

    joined = {}

    def fake_join(mp3_files, output_file):
        joined["mp3_files"] = mp3_files
        joined["output_file"] = output_file

    monkeypatch.setattr("homeaudio.vcal.school_announcements.core.join_mp3s_to_wav", fake_join)

    output_file = build_audio_file(["Sentence one.", "Sentence two."])

    assert joined["mp3_files"] == [PRE_ANNOUNCEMENT_BELL, "speech1.mp3", "speech2.mp3", POST_ANNOUNCEMENT_SILENCE]
    assert output_file == joined["output_file"]
    assert output_file.startswith(f"{OUTPUT_AUDIO_DIRECTORY}/school_announcement_")
    assert output_file.endswith(".wav")


def test_seconds_until_returns_seconds_remaining_before_target_time():
    now = datetime(2026, 9, 8, 8, 29, 0)

    assert _seconds_until(time_of_day(8, 30, 0), now) == 60.0


def test_seconds_until_returns_zero_when_target_time_has_passed():
    now = datetime(2026, 9, 8, 8, 31, 0)

    assert _seconds_until(time_of_day(8, 30, 0), now) == 0.0


def test_seconds_until_returns_zero_when_target_time_is_now():
    now = datetime(2026, 9, 8, 8, 30, 0)

    assert _seconds_until(time_of_day(8, 30, 0), now) == 0.0


def test_play_school_announcements_sleeps_until_the_scheduled_time_before_playing(monkeypatch):
    fake_settings = SimpleNamespace(
        holiday_keywords=[],
        school_event_keywords=["school"],
    )

    class FakeCalendarSource:
        def __init__(self, cache_file_path):
            pass

        def load_data_from_file(self):
            return None

    monkeypatch.setattr(school_announcements_core, "SchoolAnnouncementsSettings", lambda: fake_settings)
    monkeypatch.setattr(school_announcements_core, "CalendarSource", FakeCalendarSource)
    monkeypatch.setattr(school_announcements_core, "get_events_for_date", lambda calendar_days, base_time: [])
    monkeypatch.setattr(school_announcements_core, "text_to_voice_file", lambda sentence, tld: "speech.mp3")
    monkeypatch.setattr(school_announcements_core, "join_mp3s_to_wav", lambda files, output: None)

    seen_target_times = []
    monkeypatch.setattr(
        school_announcements_core,
        "_seconds_until",
        lambda target_time, now: seen_target_times.append(target_time) or 42.0,
    )

    calls = []
    monkeypatch.setattr(school_announcements_core.time_module, "sleep", lambda seconds: calls.append(("sleep", seconds)))
    monkeypatch.setattr(school_announcements_core, "play_tts_audio_file", lambda *args, **kwargs: calls.append(("play", None)))

    play_school_announcements(play_time=time_of_day(8, 30, 0))

    assert seen_target_times == [time_of_day(8, 30, 0)]
    assert calls == [("sleep", 42.0), ("play", None)]


def test_play_school_announcements_does_not_sleep_when_no_play_time_given(monkeypatch):
    fake_settings = SimpleNamespace(
        holiday_keywords=[],
        school_event_keywords=["school"],
    )

    class FakeCalendarSource:
        def __init__(self, cache_file_path):
            pass

        def load_data_from_file(self):
            return None

    monkeypatch.setattr(school_announcements_core, "SchoolAnnouncementsSettings", lambda: fake_settings)
    monkeypatch.setattr(school_announcements_core, "CalendarSource", FakeCalendarSource)
    monkeypatch.setattr(school_announcements_core, "get_events_for_date", lambda calendar_days, base_time: [])
    monkeypatch.setattr(school_announcements_core, "text_to_voice_file", lambda sentence, tld: "speech.mp3")
    monkeypatch.setattr(school_announcements_core, "join_mp3s_to_wav", lambda files, output: None)

    calls = []
    monkeypatch.setattr(school_announcements_core.time_module, "sleep", lambda seconds: calls.append(("sleep", seconds)))
    monkeypatch.setattr(school_announcements_core, "play_tts_audio_file", lambda *args, **kwargs: calls.append(("play", None)))

    play_school_announcements()

    assert calls == [("play", None)]


def test_is_school_holiday_true_when_holiday_keyword_matches_case_insensitively():
    events = [
        Event(owner="cal", summary="no SCHOOL today", description="", calendar_id="id"),
    ]

    assert is_school_holiday(events, DEFAULT_HOLIDAY_KEYWORDS) is True


def test_is_school_holiday_true_for_configured_keyword():
    events = [
        Event(owner="cal", summary="Public Holiday", description="", calendar_id="id"),
    ]

    assert is_school_holiday(events, ["public holiday"]) is True


def test_is_school_holiday_false_when_no_keyword_matches():
    events = [
        Event(owner="cal", summary="School Assembly", description="", calendar_id="id"),
    ]

    assert is_school_holiday(events, DEFAULT_HOLIDAY_KEYWORDS) is False
