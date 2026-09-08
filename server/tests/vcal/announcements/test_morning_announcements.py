import sys
from datetime import datetime, time as time_of_day
from pathlib import Path
from unittest.mock import Mock

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

import homeaudio.vcal.morning_announcements.core as morning_announcements_core
from homeaudio.vcal.morning_announcements.core import TextBuilder, _seconds_until, play_morning_announcements
from homeaudio.vcal.cal.google_calendar import Event, WeatherForecast

select_option_call_count = 0

def fake_select_option(opts):
    global select_option_call_count
    select_option_call_count += 1
    if select_option_call_count == 1:
        return Mock(text="Prelude text.")
    return Mock(text="Selected fact")

def test_get_morning_announcements_text_includes_weather_and_facts(monkeypatch):
    # Create three events: two normal and one weather forecast
    e1 = Event(owner="cal", summary="Meeting", description="", calendar_id="id")
    e2 = Event(owner="cal", summary="Appointment", description="", calendar_id="id")
    weather = WeatherForecast(owner="cal", summary="Min 10 Max 20", description="", calendar_id="id")

    events = [weather, e1, e2]

    monkeypatch.setattr(
        "homeaudio.vcal.morning_announcements.core.select_option",
        fake_select_option,
    )

    # Provide a minimal settings object with needed attributes
    settings = Mock()
    settings.enabled_prelude_options = ["Prelude text."]
    settings.prelude_probability = 1.0
    settings.unused_facts = ["fact1"]
    settings.save = Mock()

    tb = TextBuilder(events, settings)

    text = tb.get_morning_announcements_text()

    expected = [ "Good morning!",
        "Prelude text.",
        "The weather forecast for today is: Min 10 Max 20.",
        "Todays events are:",
        "Meeting.",
        "Appointment.",
        "Your fun fact for today is:",
        "Selected fact",
        "Have a lovely day.",
    ]
    assert text == expected


def test_seconds_until_returns_seconds_remaining_before_target_time():
    now = datetime(2026, 9, 8, 7, 16, 0)

    assert _seconds_until(time_of_day(7, 17, 0), now) == 60.0


def test_seconds_until_returns_zero_when_target_time_has_passed():
    now = datetime(2026, 9, 8, 7, 18, 0)

    assert _seconds_until(time_of_day(7, 17, 0), now) == 0.0


def test_seconds_until_returns_zero_when_target_time_is_now():
    now = datetime(2026, 9, 8, 7, 17, 0)

    assert _seconds_until(time_of_day(7, 17, 0), now) == 0.0


class _FakeCalendarSource:
    def __init__(self, cache_file_path):
        pass

    def load_data_from_file(self):
        return None


class _FakeAudioFileBuilder:
    def __init__(self, text_builder, bg_music_selector):
        pass

    def build_audio_file(self):
        return "output.wav"


def test_play_morning_announcements_sleeps_until_the_scheduled_time_before_playing(monkeypatch):
    monkeypatch.setattr(morning_announcements_core, "CalendarSource", _FakeCalendarSource)
    monkeypatch.setattr(morning_announcements_core, "get_events_for_date", lambda calendar_days, base_time: [])
    monkeypatch.setattr(morning_announcements_core, "AudioFileBuilder", _FakeAudioFileBuilder)

    seen_target_times = []
    monkeypatch.setattr(
        morning_announcements_core,
        "_seconds_until",
        lambda target_time, now: seen_target_times.append(target_time) or 42.0,
    )

    calls = []
    monkeypatch.setattr(morning_announcements_core.time_module, "sleep", lambda seconds: calls.append(("sleep", seconds)))
    monkeypatch.setattr(morning_announcements_core, "play_morning_announcements_audio_file", lambda *args, **kwargs: calls.append(("play", None)))

    play_morning_announcements(play_time=time_of_day(7, 17, 0))

    assert seen_target_times == [time_of_day(7, 17, 0)]
    assert calls == [("sleep", 42.0), ("play", None)]


def test_play_morning_announcements_does_not_sleep_when_no_play_time_given(monkeypatch):
    monkeypatch.setattr(morning_announcements_core, "CalendarSource", _FakeCalendarSource)
    monkeypatch.setattr(morning_announcements_core, "get_events_for_date", lambda calendar_days, base_time: [])
    monkeypatch.setattr(morning_announcements_core, "AudioFileBuilder", _FakeAudioFileBuilder)

    calls = []
    monkeypatch.setattr(morning_announcements_core.time_module, "sleep", lambda seconds: calls.append(("sleep", seconds)))
    monkeypatch.setattr(morning_announcements_core, "play_morning_announcements_audio_file", lambda *args, **kwargs: calls.append(("play", None)))

    play_morning_announcements()

    assert calls == [("play", None)]
