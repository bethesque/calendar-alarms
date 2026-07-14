import sys
from pathlib import Path
from unittest.mock import Mock

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from vcal.announcements.morning_announcements import TextBuilder
from vcal.cal.google_calendar import Event, WeatherForecast


def test_get_morning_announcements_text_includes_weather_and_facts(monkeypatch):
    # Create three events: two normal and one weather forecast
    e1 = Event(owner="cal", summary="Meeting", description="")
    e2 = Event(owner="cal", summary="Appointment", description="")
    weather = WeatherForecast(owner="cal", summary="Min 10 Max 20", description="")

    events = [weather, e1, e2]

    # Stub select_text and select_option
    monkeypatch.setattr("vcal.announcements.morning_announcements.select_text", lambda *a, **k: "Prelude text.")
    monkeypatch.setattr("vcal.announcements.morning_announcements.select_option", lambda opts: Mock(text="Selected fact"))

    # Provide a minimal settings object with needed attributes
    settings = Mock()
    settings.prelude_options = []
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
